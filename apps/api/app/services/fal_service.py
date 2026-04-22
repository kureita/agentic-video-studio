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
expects (image, video, tts, music, sfx, lipsync) and normalize the response
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
    """Raised when a fal submission fails before the request is enqueued."""


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
                raise FalSubmitError(f"fal submit failed: {e}") from e
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
            raise FalSubmitError(f"fal subscribe failed: {e}") from e
        return {"mode": "sync", "output": output}

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
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("[Fal] dispatch error for %s: %s", endpoint_id, e)
            return {"success": False, "error": str(e)}

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
        attempts: int = 4,
        initial_backoff_s: float = 0.5,
    ) -> Optional[float]:
        """Fetch the authoritative billable units for a completed request.

        Fal exposes the real billed quantity via the `X-Fal-Billable-Units`
        response header on `GET /{endpoint_id}/requests/{request_id}`. This is
        the number Fal multiplies by `unit_price` to compute the charge, so we
        must use it instead of hand-rolled estimates (per-second, per-image...).

        The endpoint may briefly return 202 if the response artefact hasn't
        landed yet on fal's side, so we retry with exponential backoff.

        Returns None if the header can't be recovered — callers should fall
        back to registry pricing only as a last resort.
        """
        if not settings.fal_api_key:
            logger.warning("[Fal] fetch_billable_units: FAL_API_KEY not set")
            return None
        if not endpoint_id or not request_id:
            return None

        url = f"{_QUEUE_BASE}/{endpoint_id.lstrip('/')}/requests/{request_id}"
        headers = {"Authorization": f"Key {settings.fal_api_key}"}

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
            for attempt in range(attempts):
                try:
                    resp = await client.get(url, headers=headers)
                except httpx.HTTPError as e:
                    logger.warning(
                        "[Fal] fetch_billable_units attempt %s failed for %s: %s",
                        attempt + 1, request_id, e,
                    )
                    await asyncio.sleep(initial_backoff_s * (2 ** attempt))
                    continue

                raw = (
                    resp.headers.get("X-Fal-Billable-Units")
                    or resp.headers.get("x-fal-billable-units")
                )
                if raw is not None:
                    try:
                        return float(raw)
                    except ValueError:
                        logger.warning(
                            "[Fal] billable units header is not numeric: %r", raw
                        )
                        return None

                # 202 Accepted — result not yet materialized, try again.
                if resp.status_code == 202:
                    await asyncio.sleep(initial_backoff_s * (2 ** attempt))
                    continue

                # 200 without the header → fal didn't emit billable units for this run.
                logger.info(
                    "[Fal] no X-Fal-Billable-Units on response for request_id=%s "
                    "(status=%s)",
                    request_id, resp.status_code,
                )
                return None

        logger.warning(
            "[Fal] gave up fetching billable units for request_id=%s", request_id
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
    def build_tts_args(*, text: str, voice: Optional[str] = None) -> dict[str, Any]:
        args: dict[str, Any] = {"text": text}
        if voice:
            args["voice"] = voice
            args["voice_setting"] = {"voice_id": voice}
        return args

    @staticmethod
    def build_music_args(*, prompt: str, duration_s: int = 30) -> dict[str, Any]:
        return {
            "prompt": prompt,
            "music_length_ms": int(duration_s * 1000),
            "duration_seconds": int(duration_s),
        }

    @staticmethod
    def build_sfx_args(*, prompt: str, duration_s: Optional[float] = None) -> dict[str, Any]:
        args: dict[str, Any] = {"text": prompt, "prompt": prompt}
        if duration_s:
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

        Returns one of:
          * `{"success": True, "image_url": ...}`
          * `{"success": True, "video_url": ..., "duration": ...}`
          * `{"success": True, "audio_url": ..., "duration": ...}`
          * `{"success": False, "error": ...}`
        """
        if not isinstance(payload, dict):
            return {"success": False, "error": "empty fal payload"}

        cap = (capability or "").lower()

        if cap in ("t2i", "i2i", "image"):
            images = payload.get("images") or []
            if images and isinstance(images, list):
                url = images[0].get("url") if isinstance(images[0], dict) else None
                if url:
                    return {"success": True, "image_url": url}
            url = payload.get("image", {}).get("url") if isinstance(payload.get("image"), dict) else payload.get("image_url")
            if url:
                return {"success": True, "image_url": url}

        if cap in ("t2v", "i2v", "video", "lipsync"):
            video = payload.get("video")
            url = None
            duration: Optional[float] = None
            if isinstance(video, dict):
                url = video.get("url")
                duration = video.get("duration")
            elif isinstance(video, str):
                url = video
            url = url or payload.get("video_url")
            if url:
                return {
                    "success": True,
                    "video_url": url,
                    **({"duration": duration} if duration is not None else {}),
                }

        if cap in ("tts", "music", "sfx", "t2m", "t2sfx", "audio"):
            audio = payload.get("audio")
            url = None
            duration: Optional[float] = None
            if isinstance(audio, dict):
                url = audio.get("url")
                duration = audio.get("duration")
            elif isinstance(audio, str):
                url = audio
            url = url or payload.get("audio_url")
            if url:
                return {
                    "success": True,
                    "audio_url": url,
                    **({"duration": duration} if duration is not None else {}),
                }

        return {"success": False, "error": f"no output url found in fal payload (capability={capability})"}
