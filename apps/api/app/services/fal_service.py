"""
FalService — single entry point for image / video / audio generation on fal.ai.

Dispatch strategy
─────────────────
* Webhook mode (default in production): when `FAL_WEBHOOK_PUBLIC_URL` is set,
  `submit()` posts the job to fal's queue with `webhook_url` set to our
  `/api/fal/webhook` endpoint and returns immediately with the request id.
  The caller persists correlation state in `fal_jobs`, marks the workflow task
  as `waiting_webhook` and lets the Lambda exit.
* Sync mode (local dev): when the webhook url is empty, `submit()` falls back
  to `fal_client.subscribe_async` and blocks until the result is ready.

Per-capability adapters shape arguments into what each family of endpoints
expects (image, video, voice design/clone, music, sfx, lipsync) and normalize the response
into a flat dict with `image_url` | `video_url` | `audio_url`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import fal_client
import httpx

from app.core.config import settings
from app.services.fal_context import current_context

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/api/fal/webhook"
_QUEUE_BASE = "https://queue.fal.run"


class FalSubmitError(RuntimeError):
    """Raised when a fal submission fails before the request is enqueued.

    When the underlying error came from fal's HTTP layer (e.g. a 404 for an
    unknown endpoint), `request_id` / `billable_units` / `status_code` /
    `response_headers` are populated so the caller can persist a failed
    `fal_jobs` row and charge the user for the (small) amount fal billed us.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        billable_units: Optional[float] = None,
        response_headers: Optional[dict[str, str]] = None,
        error_type: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        self.billable_units = billable_units
        self.response_headers = response_headers or {}
        self.error_type = error_type


class FalService:
    """Thin wrapper around fal_client with webhook-first dispatch."""

    def __init__(self) -> None:
        if settings.fal_api_key:
            os.environ["FAL_KEY"] = settings.fal_api_key
        self._webhook_base = (settings.fal_webhook_public_url or "").rstrip("/")

    # ------------------------------------------------------------------
    # Mode helpers
    # ------------------------------------------------------------------
    @property
    def webhook_mode(self) -> bool:
        """Webhook mode is active iff a public callback url is configured."""
        return bool(self._webhook_base)

    @property
    def webhook_url(self) -> Optional[str]:
        return f"{self._webhook_base}{WEBHOOK_PATH}" if self._webhook_base else None

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------
    async def submit(
        self,
        endpoint_id: str,
        arguments: dict[str, Any],
        *,
        timeout_s: int = 600,
    ) -> dict[str, Any]:
        """Submit a job.

        Returns one of:
          * `{"mode": "webhook", "request_id": "..."}`  — job enqueued, result via webhook
          * `{"mode": "sync", "output": {...}}`        — run completed inline
        """
        if not settings.fal_api_key:
            raise FalSubmitError("FAL_API_KEY is not configured")

        if self.webhook_mode:
            try:
                handler = await fal_client.submit_async(
                    endpoint_id,
                    arguments=arguments,
                    webhook_url=self.webhook_url,
                )
            except Exception as e:
                logger.exception("[Fal] submit failed for %s: %s", endpoint_id, e)
                raise self._wrap_submit_error("fal submit failed", e) from e
            logger.info(
                "[Fal] submit endpoint=%s mode=webhook request_id=%s callback=%s",
                endpoint_id, handler.request_id, self.webhook_url,
            )
            return {"mode": "webhook", "request_id": handler.request_id}

        # Sync fallback (local dev)
        logger.info("[Fal] subscribe endpoint=%s mode=sync (no FAL_WEBHOOK_PUBLIC_URL)", endpoint_id)
        try:
            output = await fal_client.subscribe_async(
                endpoint_id,
                arguments=arguments,
                with_logs=False,
                client_timeout=timeout_s,
            )
        except Exception as e:
            logger.exception("[Fal] subscribe failed for %s: %s", endpoint_id, e)
            raise self._wrap_submit_error("fal subscribe failed", e) from e
        return {"mode": "sync", "output": output}

    @staticmethod
    def _wrap_submit_error(prefix: str, exc: Exception) -> "FalSubmitError":
        """Convert a fal_client exception to FalSubmitError, pulling out the
        request id / billable units / status code from the response headers
        when they're present (so the caller can charge the failed-submit cost).
        """
        from fal_client.client import FalClientHTTPError  # type: ignore

        message = f"{prefix}: {exc}"
        if isinstance(exc, FalClientHTTPError):
            headers = exc.response_headers or {}
            # Header names are lower-cased on the way in by httpx but be
            # tolerant — try both.
            def _h(key: str) -> Optional[str]:
                return headers.get(key) or headers.get(key.lower()) or headers.get(key.title())

            rid = _h("x-fal-request-id") or _h("X-Fal-Request-Id")
            raw_units = _h("x-fal-billable-units")
            units: Optional[float] = None
            if raw_units is not None:
                try:
                    units = float(raw_units)
                except (TypeError, ValueError):
                    units = None
            detail = None
            for attr in ("response_text", "response_body", "body", "detail"):
                value = getattr(exc, attr, None)
                if value:
                    detail = str(value)
                    break

            user_friendly_message = "Generation failed due to an unexpected error."
            if exc.status_code == 422:
                user_friendly_message = "Invalid input parameters. Please check your prompt or reference media."
            elif exc.status_code == 404:
                user_friendly_message = "The requested model is currently unavailable."
            elif exc.status_code in (401, 403):
                user_friendly_message = "Authentication with the generation provider failed."
            elif exc.status_code and exc.status_code >= 500:
                user_friendly_message = "The generation provider is experiencing issues. Please try again later."
            elif exc.status_code == 400:
                user_friendly_message = "The provider rejected the request. Please check your inputs."

            if detail:
                detail_lower = detail.lower()
                if "nsfw" in detail_lower or "content policy" in detail_lower or "safety" in detail_lower:
                    user_friendly_message = "Your request was flagged by the content filter. Please modify your prompt or media and try again."

            return FalSubmitError(
                user_friendly_message,
                status_code=exc.status_code,
                request_id=rid,
                billable_units=units,
                response_headers=dict(headers),
                error_type=getattr(exc, "error_type", None),
            )
        return FalSubmitError(message)

    async def dispatch_for_generator(
        self,
        *,
        capability: str,
        endpoint_id: str,
        arguments: dict[str, Any],
        model_info: Optional[dict[str, Any]] = None,
        args_meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Submit a job from inside a generator.

        Decision matrix:
          * webhook_mode AND we're inside a workflow task (contextvar set):
            submit async → persist `fal_jobs` correlation row → return
            `{success, status='pending_fal', request_id, capability, endpoint_id, ...}`.
          * otherwise:
            subscribe synchronously → return `{success, raw_output: <fal payload>}`
            for the generator to post-process.

        Failure shape: `{"success": False, "error": str}`.
        """
        model_info = model_info or {}
        ctx = current_context()
        use_webhook = self.webhook_mode and ctx is not None
        logger.info(
            "[Fal] dispatch capability=%s endpoint=%s mode=%s ctx=%s model=%s",
            capability, endpoint_id,
            "webhook" if use_webhook else ("sync-drain" if self.webhook_mode else "sync"),
            bool(ctx), model_info.get("name"),
        )

        try:
            if use_webhook:
                submit = await self.submit(endpoint_id, arguments)
                if submit["mode"] != "webhook":
                    return {"success": True, "raw_output": submit.get("output")}
                request_id = submit["request_id"]
                await self._persist_fal_job(
                    request_id=request_id,
                    capability=capability,
                    endpoint_id=endpoint_id,
                    arguments=arguments,
                    ctx=ctx,
                    args_meta=args_meta,
                    model_info=model_info,
                )
                return {
                    "success": True,
                    "status": "pending_fal",
                    "request_id": request_id,
                    "capability": capability,
                    "endpoint_id": endpoint_id,
                    "model": model_info.get("name"),
                    "provider": model_info.get("provider"),
                }

            submit = await self.submit(endpoint_id, arguments)
            if submit["mode"] == "webhook":
                # No ctx ⇒ caller needs a terminal result. Drain the queue.
                status = await self.fetch_result(endpoint_id, submit["request_id"])
                if status["status"] != "COMPLETED":
                    return {
                        "success": False,
                        "error": f"fal job stuck in {status['status']}",
                    }
                return {"success": True, "raw_output": status["output"]}
            return {"success": True, "raw_output": submit["output"]}
        except FalSubmitError as e:
            # Submit-time failures (4xx/5xx from fal before the job enqueues)
            # still get billed — fal returns ~$0.000043 on a 404 for an
            # unknown endpoint. Persist a `fal_jobs` row + charge the user
            # the small amount so the billing UI matches fal's invoice.
            await self._record_failed_submit(
                error=e,
                capability=capability,
                endpoint_id=endpoint_id,
                arguments=arguments,
                ctx=ctx,
                args_meta=args_meta,
                model_info=model_info,
            )
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("[Fal] dispatch error for %s: %s", endpoint_id, e)
            return {"success": False, "error": str(e)}

    async def _record_failed_submit(
        self,
        *,
        error: "FalSubmitError",
        capability: str,
        endpoint_id: str,
        arguments: dict[str, Any],
        ctx: Optional[dict[str, Any]],
        args_meta: Optional[dict[str, Any]],
        model_info: dict[str, Any],
    ) -> None:
        """Persist + bill for a fal call that fal rejected before queueing."""
        from datetime import datetime, timezone
        from app.core.database import get_database, get_fal_jobs_collection

        rid = error.request_id or f"failed-submit-{datetime.now(timezone.utc).timestamp()}"
        now = datetime.now(timezone.utc)

        # Compute cost from the response header if fal gave us one.
        cost_usd = 0.0
        cost_info: dict[str, Any] = {}
        if error.billable_units is not None and error.billable_units > 0:
            try:
                from app.services.fal_pricing import FalPricingService
                pricing = FalPricingService(get_database())
                cost_info = await pricing.compute_cost_usd(
                    endpoint_id,
                    billable_units=error.billable_units,
                    duration_s=(args_meta or {}).get("duration"),
                    chars=(args_meta or {}).get("chars"),
                    resolution_label=(args_meta or {}).get("resolution"),
                    aspect_ratio=(args_meta or {}).get("aspect_ratio"),
                )
                cost_usd = float(cost_info.get("cost_usd") or 0.0)
            except Exception as e:
                logger.warning("[Fal] failed-submit pricing error: %s", e)

        try:
            fal_jobs = get_fal_jobs_collection()
            await fal_jobs.update_one(
                {"request_id": rid},
                {
                    "$setOnInsert": {
                        "request_id": rid,
                        "capability": capability,
                        "endpoint_id": endpoint_id,
                        "arguments": arguments,
                        "args_meta": args_meta or {},
                        "context": ctx or {},
                        "model_name": model_info.get("name"),
                        "provider": model_info.get("provider", "fal.ai"),
                        "submitted_at": now,
                    },
                    "$set": {
                        "status": "failed",
                        "completed_at": now,
                        "error": str(error),
                        "error_status_code": error.status_code,
                        "error_type": error.error_type,
                        "billable_units": error.billable_units,
                        "cost_usd": cost_usd,
                        "unit": cost_info.get("unit"),
                        "unit_price": cost_info.get("unit_price"),
                        "price_source": cost_info.get("source"),
                        "cost_resolution": cost_info.get("resolution"),
                    },
                },
                upsert=True,
            )
        except Exception as e:
            logger.warning("[Fal] failed-submit persist error: %s", e)

        if cost_usd > 0 and ctx:
            try:
                # Lazy import to avoid a circular: fal_service is imported by
                # fal_webhook which already imports billing.
                from app.api.endpoints.fal_webhook import _charge_billing
                await _charge_billing(
                    cost_usd,
                    ctx.get("node_type"),
                    ctx.get("user_id"),
                    model_info.get("name", endpoint_id),
                    model_info.get("provider", "fal.ai"),
                    ctx.get("workflow_id"),
                    ctx.get("node_id"),
                    billing_meta={
                        "request_id": rid,
                        "endpoint_id": endpoint_id,
                        "billable_units": error.billable_units,
                        "unit": cost_info.get("unit"),
                        "unit_price": cost_info.get("unit_price"),
                        "price_source": cost_info.get("source"),
                        "cost_resolution": cost_info.get("resolution"),
                        "fal_error": str(error),
                        "fal_status_code": error.status_code,
                        "outcome": "failed_at_submit",
                    },
                )
                logger.info(
                    "[Fal] charged $%.6f for failed submit endpoint=%s rid=%s",
                    cost_usd, endpoint_id, rid,
                )
            except Exception as e:
                logger.warning("[Fal] failed-submit charge error: %s", e)

    async def _persist_fal_job(
        self,
        *,
        request_id: str,
        capability: str,
        endpoint_id: str,
        arguments: dict[str, Any],
        ctx: dict[str, Any],
        args_meta: Optional[dict[str, Any]],
        model_info: dict[str, Any],
    ) -> None:
        """Persist correlation row so the webhook / sweeper can finish the job."""
        from app.core.database import get_fal_jobs_collection

        collection = get_fal_jobs_collection()
        doc = {
            "request_id": request_id,
            "status": "waiting_webhook",
            "capability": capability,
            "endpoint_id": endpoint_id,
            "arguments": arguments,
            "args_meta": args_meta or {},
            "context": ctx,
            "model_name": model_info.get("name"),
            "provider": model_info.get("provider"),
            "submitted_at": datetime.now(timezone.utc),
        }
        try:
            await collection.update_one(
                {"request_id": request_id}, {"$setOnInsert": doc}, upsert=True
            )
        except Exception as e:
            logger.warning("[Fal] failed to persist fal_jobs entry %s: %s", request_id, e)

    async def fetch_billable_units(
        self,
        endpoint_id: str,
        request_id: str,
        *,
        attempts: int = 8,
        initial_backoff_s: float = 0.6,
        max_backoff_s: float = 6.0,
    ) -> Optional[float]:
        """Fetch the authoritative billable units for a completed request.

        Fal exposes the real billed quantity via the `X-Fal-Billable-Units`
        response header on `GET /{endpoint_id}/requests/{request_id}`. This is
        the number Fal multiplies by `unit_price` to compute the charge, so we
        must use it instead of hand-rolled estimates (per-second, per-image...).

        The endpoint may briefly 202 if the result artefact hasn't landed yet,
        and even after 200 the header sometimes lags by a few hundred ms. We
        retry aggressively (8 attempts, exponential backoff capped at 6s,
        ~25s total) because dropping back to the per-second/per-run estimate
        meaningfully under- or over-charges the user vs fal's invoice.

        Returns None only if fal still won't tell us after the full retry
        window — callers should then use the config-matched estimate, NOT the
        per-run default.
        """
        if not settings.fal_api_key:
            logger.warning("[Fal] fetch_billable_units: FAL_API_KEY not set")
            return None
        if not endpoint_id or not request_id:
            return None

        # Build the queue URL the same way fal_client does. The queue endpoint
        # only knows about `{namespace?}/{owner}/{alias}` — the sub-path
        # (e.g. "fast/reference-to-video" on "bytedance/seedance-2.0/fast/...")
        # is part of the model's invocation address but NOT part of the queue
        # request URL. Hitting the full sub-path returns HTTP 405 silently.
        try:
            from fal_client.client import AppId
            app_id = AppId.from_endpoint_id(endpoint_id)
            prefix = f"{app_id.namespace}/" if app_id.namespace else ""
            queue_path = f"{prefix}{app_id.owner}/{app_id.alias}"
        except Exception as e:
            logger.warning(
                "[Fal] could not parse endpoint_id=%r: %s — falling back to raw path",
                endpoint_id, e,
            )
            queue_path = endpoint_id.lstrip("/")

        url = f"{_QUEUE_BASE}/{queue_path}/requests/{request_id}"
        headers = {"Authorization": f"Key {settings.fal_api_key}"}

        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=3.0)) as client:
            for attempt in range(attempts):
                backoff = min(max_backoff_s, initial_backoff_s * (2 ** attempt))
                try:
                    resp = await client.get(url, headers=headers)
                except httpx.HTTPError as e:
                    logger.warning(
                        "[Fal] fetch_billable_units attempt %s/%s network error for %s: %s",
                        attempt + 1, attempts, request_id, e,
                    )
                    await asyncio.sleep(backoff)
                    continue

                raw = (
                    resp.headers.get("X-Fal-Billable-Units")
                    or resp.headers.get("x-fal-billable-units")
                )
                if raw is not None:
                    try:
                        units = float(raw)
                        logger.info(
                            "[Fal] fetched billable_units=%s for request_id=%s "
                            "on attempt %s/%s",
                            units, request_id, attempt + 1, attempts,
                        )
                        return units
                    except ValueError:
                        logger.warning(
                            "[Fal] billable units header is not numeric: %r", raw
                        )
                        return None

                # 202 Accepted — result still being prepared, try again soon.
                if resp.status_code == 202:
                    logger.info(
                        "[Fal] result still 202 for %s, retrying in %.1fs (attempt %s/%s)",
                        request_id, backoff, attempt + 1, attempts,
                    )
                    await asyncio.sleep(backoff)
                    continue

                # 200 without header → header may lag the body. Retry a few
                # more times before giving up; only return None on the last
                # attempt so transient lag doesn't drop us into the estimate.
                if resp.status_code == 200:
                    if attempt < attempts - 1:
                        logger.info(
                            "[Fal] 200 without X-Fal-Billable-Units for %s, "
                            "retrying in %.1fs (attempt %s/%s)",
                            request_id, backoff, attempt + 1, attempts,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    logger.warning(
                        "[Fal] no X-Fal-Billable-Units for request_id=%s "
                        "after %s attempts (status=200)",
                        request_id, attempts,
                    )
                    return None

                # Other status (4xx/5xx) — log and back off
                logger.warning(
                    "[Fal] fetch_billable_units request_id=%s got HTTP %s "
                    "on attempt %s/%s",
                    request_id, resp.status_code, attempt + 1, attempts,
                )
                await asyncio.sleep(backoff)

        logger.warning(
            "[Fal] gave up fetching billable_units for request_id=%s after %s attempts",
            request_id, attempts,
        )
        return None

    async def fetch_result(self, endpoint_id: str, request_id: str) -> dict[str, Any]:
        """Fetch the final result of a previously-submitted request.

        Used by the missed-webhook sweeper when a pending job has been quiet
        for too long. Returns `{"status": "IN_QUEUE"|"IN_PROGRESS"|"COMPLETED",
        "output": {...} | None, "error": str | None}`.
        """
        try:
            status = await fal_client.status_async(endpoint_id, request_id, with_logs=False)
        except Exception as e:
            logger.warning("[Fal] status poll failed for %s: %s", request_id, e)
            return {"status": "UNKNOWN", "output": None, "error": str(e)}

        status_name = getattr(status, "__class__", type(status)).__name__.upper()
        # fal_client types: Queued / InProgress / Completed
        if "COMPLETED" in status_name:
            try:
                output = await fal_client.result_async(endpoint_id, request_id)
                return {"status": "COMPLETED", "output": output, "error": None}
            except Exception as e:
                return {"status": "COMPLETED", "output": None, "error": str(e)}
        if "INPROGRESS" in status_name:
            return {"status": "IN_PROGRESS", "output": None, "error": None}
        return {"status": "IN_QUEUE", "output": None, "error": None}

    # ------------------------------------------------------------------
    # Argument builders — per capability
    # ------------------------------------------------------------------
    @staticmethod
    def build_image_args(
        *,
        prompt: str,
        aspect_ratio: str = "1:1",
        reference_image_urls: Optional[list[str]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        negative_prompt: Optional[str] = None,
        num_images: int = 1,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"prompt": prompt, "num_images": num_images}
        if width and height:
            args["image_size"] = {"width": width, "height": height}
        else:
            args["aspect_ratio"] = aspect_ratio
        if reference_image_urls:
            # Most fal image models accept either `image_urls` (plural) or `image_url` (single);
            # we send both common shapes — unused keys are ignored by most runners.
            args["image_urls"] = reference_image_urls
            args["image_url"] = reference_image_urls[0]
        if negative_prompt:
            args["negative_prompt"] = negative_prompt
        return args

    @staticmethod
    def build_video_args(
        *,
        prompt: str,
        duration: int = 8,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        image_url: Optional[str] = None,
        end_image_url: Optional[str] = None,
        generate_audio: bool = False,
        negative_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "enable_audio": generate_audio,
        }
        if image_url:
            args["image_url"] = image_url
        if end_image_url:
            args["end_image_url"] = end_image_url
            args["tail_image_url"] = end_image_url
        if negative_prompt:
            args["negative_prompt"] = negative_prompt
        return args

    @staticmethod
    def build_voice_design_args(*, prompt: str, preview_text: str) -> dict[str, Any]:
        return {"prompt": prompt, "preview_text": preview_text}

    @staticmethod
    def build_voice_clone_args(
        *,
        audio_url: str,
        text: Optional[str] = None,
        model: str = "speech-02-hd",
        noise_reduction: Optional[bool] = None,
        need_volume_normalization: Optional[bool] = None,
        accuracy: Optional[float] = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"audio_url": audio_url, "model": model}
        if text:
            args["text"] = text
        if noise_reduction is not None:
            args["noise_reduction"] = noise_reduction
        if need_volume_normalization is not None:
            args["need_volume_normalization"] = need_volume_normalization
        if accuracy is not None:
            args["accuracy"] = accuracy
        return args

    @staticmethod
    def build_music_args(*, prompt: str, duration_s: Optional[float] = None) -> dict[str, Any]:
        args: dict[str, Any] = {"prompt": prompt}
        if duration_s is not None:
            args["music_length_ms"] = int(duration_s * 1000)
        return args

    @staticmethod
    def build_sfx_args(*, prompt: str, duration_s: Optional[float] = None) -> dict[str, Any]:
        args: dict[str, Any] = {"text": prompt, "prompt": prompt}
        if duration_s is not None:
            args["duration_seconds"] = float(duration_s)
        return args

    @staticmethod
    def build_lipsync_args(*, video_url: str, audio_url: str) -> dict[str, Any]:
        return {"video_url": video_url, "audio_url": audio_url}

    # ------------------------------------------------------------------
    # Output normalizer — converts fal payload → flat {url, ...}
    # ------------------------------------------------------------------
    @staticmethod
    def extract_output(capability: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Normalize a fal response payload for the given capability.

        The capability is a *hint* for which output kind to prefer when a
        payload could plausibly contain more than one. If the hinted kind isn't
        present we still scan the payload for any usable media URL — fal has
        already charged for the run, so dropping the result on a capability
        mismatch (e.g. "reference"/"elements"/"v2v" video calls that weren't in
        the original allowlist) just costs the user the charge with nothing to
        show for it.

        Returns one of:
          * `{"success": True, "image_url": ...}`
          * `{"success": True, "video_url": ..., "duration": ...}`
          * `{"success": True, "audio_url": ..., "duration": ...}`
          * `{"success": False, "error": ...}`
        """
        if not isinstance(payload, dict):
            return {"success": False, "error": "empty fal payload"}

        def _video() -> dict[str, Any] | None:
            video = payload.get("video")
            url = None
            duration: Optional[float] = None
            if isinstance(video, dict):
                url = video.get("url")
                duration = video.get("duration")
            elif isinstance(video, str):
                url = video
            url = url or payload.get("video_url")
            # Some endpoints return arrays.
            if not url:
                videos = payload.get("videos")
                if isinstance(videos, list) and videos:
                    head = videos[0]
                    if isinstance(head, dict):
                        url = head.get("url")
                        duration = duration if duration is not None else head.get("duration")
                    elif isinstance(head, str):
                        url = head
            if not url:
                return None
            return {
                "success": True,
                "video_url": url,
                **({"duration": duration} if duration is not None else {}),
            }

        def _image() -> dict[str, Any] | None:
            images = payload.get("images") or []
            if images and isinstance(images, list):
                url = images[0].get("url") if isinstance(images[0], dict) else None
                if isinstance(images[0], str):
                    url = images[0]
                if url:
                    return {"success": True, "image_url": url}
            image = payload.get("image")
            url = None
            if isinstance(image, dict):
                url = image.get("url")
            elif isinstance(image, str):
                url = image
            url = url or payload.get("image_url")
            if url:
                return {"success": True, "image_url": url}
            return None

        def _audio() -> dict[str, Any] | None:
            audio = payload.get("audio")
            url = None
            duration: Optional[float] = None
            if isinstance(audio, dict):
                url = audio.get("url")
                duration = audio.get("duration")
            elif isinstance(audio, str):
                url = audio
            url = url or payload.get("audio_url")
            if not url:
                return None
            return {
                "success": True,
                "audio_url": url,
                **({"custom_voice_id": payload.get("custom_voice_id")} if payload.get("custom_voice_id") else {}),
                **({"duration": duration} if duration is not None else {}),
            }

        cap = (capability or "").lower()
        VIDEO_CAPS = {"t2v", "i2v", "v2v", "video", "lipsync", "reference", "elements", "vid2vid", "avatar"}
        IMAGE_CAPS = {"t2i", "i2i", "image"}
        AUDIO_CAPS = {"music", "sfx", "t2m", "t2sfx", "audio", "voice_design", "voice_clone"}

        if cap in VIDEO_CAPS:
            order = (_video, _image, _audio)
        elif cap in IMAGE_CAPS:
            order = (_image, _video, _audio)
        elif cap in AUDIO_CAPS:
            order = (_audio, _video, _image)
        else:
            # Unknown capability — try every kind. This is the path that used
            # to drop "reference"/"elements"/"v2v" video runs on the floor.
            order = (_video, _image, _audio)

        for extractor in order:
            result = extractor()
            if result:
                return result

        return {"success": False, "error": f"no output url found in fal payload (capability={capability})"}
