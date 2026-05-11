"""/api/fal/webhook — receives fal.ai async job callbacks.

Flow:
  1. Verify ED25519 signature via JWKS (5-min leeway, keys cached 24h).
  2. Look up the correlating `fal_jobs` row (idempotent — we ignore repeat callbacks).
  3. Normalize the payload, download the asset to S3, compute cost, charge the user,
     and write the output back into the owning `workflow_jobs` task + workflow.outputs.
  4. Re-invoke the job processor so the next task can run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request

from app.core.database import (
    get_database,
    get_fal_jobs_collection,
    get_workflow_jobs_collection,
    get_workflows_collection,
)
from app.models.usage import ActionType
from app.services.billing import BillingService
from app.services.fal_pricing import FalPricingService, extract_billable_units
from app.services.fal_service import FalService
from app.services.fal_webhook_verifier import verify_webhook_signature

router = APIRouter()
logger = logging.getLogger(__name__)

_ACTION_TYPE_MAP = {
    "imageGen": ActionType.IMAGE_GEN,
    "videoGen": ActionType.VIDEO_GEN,
    "audioGen": ActionType.AUDIO_GEN,
    "editorAgent": ActionType.RENDER,
}


@router.post("/fal/webhook")
async def fal_webhook(request: Request):
    body = await request.body()
    headers = request.headers

    request_id = headers.get("x-fal-webhook-request-id", "")
    user_id_hdr = headers.get("x-fal-webhook-user-id", "")
    timestamp = headers.get("x-fal-webhook-timestamp", "")
    signature = headers.get("x-fal-webhook-signature", "")

    logger.info(
        "[FalWebhook] inbound request_id=%s bytes=%s user=%s ts=%s",
        request_id, len(body), user_id_hdr, timestamp,
    )

    ok = await verify_webhook_signature(
        request_id=request_id,
        user_id=user_id_hdr,
        timestamp=timestamp,
        signature_hex=signature,
        body=body,
    )
    if not ok:
        logger.warning("[FalWebhook] invalid signature for request_id=%s", request_id)
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        logger.warning("[FalWebhook] bad json body for request_id=%s", request_id)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Fal does NOT include X-Fal-Billable-Units on the webhook callback itself —
    # that header is only exposed on the queue result endpoint. We still try
    # (in case fal changes this), then fall back to a direct fetch inside
    # `process_fal_callback` so the user is charged the exact amount fal bills us.
    billable_units = extract_billable_units(headers)
    status_str = str(payload.get("status") or "").upper()
    logger.info(
        "[FalWebhook] verified request_id=%s status=%s billable_units_from_headers=%s",
        request_id, status_str, billable_units,
    )

    await process_fal_callback(
        request_id=request_id,
        status=status_str,
        result=payload.get("payload"),
        error_msg=payload.get("error"),
        billable_units=billable_units,
    )

    return {"ok": True}


async def process_fal_callback(
    *,
    request_id: str,
    status: str,
    result: Any,
    error_msg: Optional[str],
    billable_units: Optional[float] = None,
    force: bool = False,
) -> None:
    """Idempotent finisher: applied by both the webhook and the missed-webhook sweeper.

    When `force=True`, the "already finalized" guard is bypassed. This is used
    by the reconcile script to recover historical failed jobs that fal actually
    completed (e.g. when a payload-extraction bug dropped the result on the
    floor). Callers should only set this when they intend to overwrite the
    existing terminal state.
    """
    fal_jobs = get_fal_jobs_collection()
    job_doc = await fal_jobs.find_one({"request_id": request_id})
    if not job_doc:
        logger.warning("[FalWebhook] unknown request_id=%s — ignoring", request_id)
        return
    if not force and job_doc.get("status") in ("completed", "failed"):
        logger.info("[FalWebhook] request_id=%s already finalized — ignoring", request_id)
        return

    ctx = job_doc.get("context") or {}
    capability = job_doc.get("capability") or "t2i"
    endpoint_id = job_doc.get("endpoint_id") or ""
    args_meta = job_doc.get("args_meta") or {}
    model_name = job_doc.get("model_name") or endpoint_id
    provider = job_doc.get("provider") or "fal.ai"

    now = datetime.now(timezone.utc)

    if status != "OK" and status != "COMPLETED":
        # fal still bills us a tiny amount on validation errors / 4xx (e.g. a
        # bad endpoint URL → 404 with `~$0.00004` charge). Persist that so the
        # user's billing matches fal's invoice byte-for-byte rather than
        # silently absorbing it.
        failed_units: Optional[float] = billable_units
        if failed_units is None:
            try:
                failed_units = await FalService().fetch_billable_units(endpoint_id, request_id)
            except Exception as e:
                logger.info(
                    "[FalWebhook] fetch_billable_units on failed run %s: %s",
                    request_id, e,
                )
        failed_cost_usd = 0.0
        failed_cost_info: dict[str, Any] = {}
        if failed_units is not None and failed_units > 0:
            try:
                pricing = FalPricingService(get_database())
                failed_cost_info = await pricing.compute_cost_usd(
                    endpoint_id,
                    billable_units=failed_units,
                    duration_s=args_meta.get("duration"),
                    chars=args_meta.get("chars"),
                    resolution_label=args_meta.get("resolution"),
                    aspect_ratio=args_meta.get("aspect_ratio"),
                )
                failed_cost_usd = float(failed_cost_info.get("cost_usd") or 0.0)
            except Exception as e:
                logger.warning("[FalWebhook] failed-run pricing error %s: %s", request_id, e)

        await fal_jobs.update_one(
            {"request_id": request_id},
            {
                "$set": {
                    "status": "failed",
                    "error": error_msg or status,
                    "completed_at": now,
                    "billable_units": failed_units,
                    "cost_usd": failed_cost_usd,
                    "unit": failed_cost_info.get("unit"),
                    "unit_price": failed_cost_info.get("unit_price"),
                    "price_source": failed_cost_info.get("source"),
                    "cost_resolution": failed_cost_info.get("resolution"),
                }
            },
        )
        await _write_task_failure(ctx, error_msg or status)

        # Still charge the user for the (small) amount fal billed us. Bypass
        # the cost==0 short-circuit in `_charge_billing` by checking here.
        if failed_cost_usd > 0:
            user_id = ctx.get("user_id")
            workflow_id = ctx.get("workflow_id")
            node_id = ctx.get("node_id")
            node_type = ctx.get("node_type")
            await _charge_billing(
                failed_cost_usd, node_type, user_id, model_name, provider,
                workflow_id, node_id,
                billing_meta={
                    "request_id": request_id,
                    "endpoint_id": endpoint_id,
                    "billable_units": failed_units,
                    "unit": failed_cost_info.get("unit"),
                    "unit_price": failed_cost_info.get("unit_price"),
                    "price_source": failed_cost_info.get("source"),
                    "cost_resolution": failed_cost_info.get("resolution"),
                    "fal_error": error_msg or status,
                    "outcome": "failed",
                },
            )
            logger.info(
                "[FalWebhook] charged $%.6f for failed run request_id=%s "
                "(fal still bills us)",
                failed_cost_usd, request_id,
            )
        return

    normalized = FalService.extract_output(capability, result)
    if not normalized.get("success"):
        await fal_jobs.update_one(
            {"request_id": request_id},
            {"$set": {"status": "failed", "error": normalized.get("error"), "completed_at": now}},
        )
        await _write_task_failure(ctx, normalized.get("error") or "fal payload missing output")
        return

    output_url = (
        normalized.get("video_url")
        or normalized.get("image_url")
        or normalized.get("audio_url")
    )
    cap_lower = str(capability or "").lower()
    video_caps = {"t2v", "i2v", "v2v", "video", "lipsync", "reference", "elements", "vid2vid", "motion", "avatar"}
    lipsync_audio_url = args_meta.get("lipsync_audio_url")
    lipsync_model_name = args_meta.get("lipsync_model")
    if cap_lower in video_caps and isinstance(lipsync_audio_url, str) and lipsync_audio_url:
        output_url = await _apply_lipsync_chain(
            output_url,
            lipsync_audio_url,
            lipsync_model_name if isinstance(lipsync_model_name, str) else None,
        )

    final_url = await _download_and_upload(output_url, capability)

    # ── Resolve billable units ────────────────────────────────────────────────
    # Webhook callbacks don't carry `X-Fal-Billable-Units`, so pull it from
    # the queue result endpoint. This is the same number fal multiplies by
    # unit_price on its invoice, so it eliminates the drift we saw where
    # token-metered models (e.g. Seedance 2.0 Fast at ~108 units/run) were
    # being charged as 1 unit/run.
    if billable_units is None:
        try:
            billable_units = await FalService().fetch_billable_units(
                endpoint_id, request_id
            )
            logger.info(
                "[FalWebhook] fetched billable_units=%s for request_id=%s endpoint=%s",
                billable_units, request_id, endpoint_id,
            )
        except Exception as e:
            logger.warning(
                "[FalWebhook] fetch_billable_units failed for %s: %s",
                request_id, e,
            )

    # Compute cost. Order of authority:
    #   1. fal's billable_units × fal's unit_price (matches their invoice)
    #   2. config-matched est_price_usd from registry (resolution+duration)
    #   3. per_run fallback from registry
    # See FalPricingService.compute_cost_usd for the full chain.
    cost_usd = 0.0
    cost_info: dict[str, Any] = {}
    try:
        pricing = FalPricingService(get_database())
        cost_info = await pricing.compute_cost_usd(
            endpoint_id,
            billable_units=billable_units,
            duration_s=normalized.get("duration") or args_meta.get("duration"),
            chars=args_meta.get("chars"),
            resolution_label=args_meta.get("resolution"),
            aspect_ratio=args_meta.get("aspect_ratio"),
        )
        cost_usd = float(cost_info.get("cost_usd") or 0.0)
        logger.info(
            "[FalWebhook] pricing request_id=%s endpoint=%s units=%.4f unit=%s "
            "unit_price=%.6f resolution=%s price_source=%s cost_usd=%.6f "
            "(billable_units_from_fal=%s)",
            request_id, endpoint_id,
            cost_info.get("units", 0.0),
            cost_info.get("unit", "?"),
            cost_info.get("unit_price", 0.0),
            cost_info.get("resolution", "?"),
            cost_info.get("source"),
            cost_usd,
            billable_units,
        )
    except Exception as e:
        logger.warning("[FalWebhook] pricing failed for %s: %s", request_id, e)

    # Persist output + mark fal_jobs done (includes audit fields so we can
    # reconstruct charges after the fact or reconcile vs fal's invoice).
    await fal_jobs.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "status": "completed",
                "completed_at": now,
                "output_url": final_url,
                "cost_usd": cost_usd,
                "billable_units": billable_units,
                "unit": cost_info.get("unit"),
                "unit_price": cost_info.get("unit_price"),
                "price_source": cost_info.get("source"),
                "cost_resolution": cost_info.get("resolution"),
            }
        },
    )

    logger.info(
        "[FalWebhook] finalized request_id=%s capability=%s output_url=%s cost_usd=%.6f",
        request_id, capability, final_url, cost_usd,
    )
    await _write_task_success(
        ctx=ctx,
        output_url=final_url,
        cost_usd=cost_usd,
        model_name=model_name,
        provider=provider,
        extra_output=normalized,
        billing_meta={
            "request_id": request_id,
            "endpoint_id": endpoint_id,
            "billable_units": billable_units,
            "unit": cost_info.get("unit"),
            "unit_price": cost_info.get("unit_price"),
            "price_source": cost_info.get("source"),
            "cost_resolution": cost_info.get("resolution"),
        },
    )


async def _download_and_upload(url: Optional[str], capability: str) -> Optional[str]:
    """Persist fal's CDN output to S3 so it never expires."""
    if not url:
        return url
    import random as _rand
    import time as _time

    import httpx

    from app.core.dependencies import get_storage_service

    storage = get_storage_service()
    cap = capability.lower()
    # Same capability buckets as `FalService.extract_output`. Without the
    # video extras (reference/elements/v2v/vid2vid) "reference"-mode video
    # outputs were uploaded with a `.mp3` extension, which then crashed the
    # browser when the URL was served back to a `<video>` element.
    VIDEO_CAPS = {"t2v", "i2v", "v2v", "video", "lipsync", "reference", "elements", "vid2vid", "motion", "avatar"}
    IMAGE_CAPS = {"t2i", "i2i", "image"}

    if cap in VIDEO_CAPS:
        ext, ctype = "mp4", "video/mp4"
    elif cap in IMAGE_CAPS:
        ext, ctype = "png", "image/png"
    else:
        ext, ctype = "mp3", "audio/mpeg"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            filename = f"fal_{int(_time.time())}_{_rand.randint(1000, 9999)}.{ext}"
            return await storage.upload_file(resp.content, filename, ctype)
        logger.warning("[FalWebhook] download failed HTTP %s — keeping cdn url", resp.status_code)
    except Exception as e:
        logger.warning("[FalWebhook] download error: %s — keeping cdn url", e)
    return url


async def _apply_lipsync_chain(
    video_url: Optional[str],
    audio_url: str,
    lipsync_model_name: Optional[str],
) -> Optional[str]:
    """Apply an optional post-generation lipsync pass in webhook mode.

    This allows workflow (async/webhook) runs to honor externally connected
    audio inputs the same way sync/local runs do.
    """
    if not video_url or not audio_url:
        return video_url
    try:
        from app.services.video_generator import VideoGenerator

        generator = VideoGenerator()
        synced_url = await generator._apply_lipsync(
            video_url,
            audio_url,
            lipsync_model_name=lipsync_model_name,
        )
        if synced_url:
            logger.info(
                "[FalWebhook] lipsync pass applied model=%s",
                lipsync_model_name or "default",
            )
            return synced_url
    except Exception as e:
        logger.warning("[FalWebhook] lipsync pass failed: %s", e)
    return video_url


async def _write_task_success(
    *,
    ctx: dict,
    output_url: Optional[str],
    cost_usd: float,
    model_name: str,
    provider: str,
    extra_output: dict,
    billing_meta: Optional[dict] = None,
) -> None:
    job_id = ctx.get("job_id")
    task_index = ctx.get("task_index")
    run_id = ctx.get("run_id")
    node_id = ctx.get("node_id")
    node_type = ctx.get("node_type")
    user_id = ctx.get("user_id")
    workflow_id = ctx.get("workflow_id")

    if not node_id or not workflow_id:
        logger.warning("[FalWebhook] incomplete context; skipping task update: %s", ctx)
        return

    # Extract start/end frames for video outputs so connected nodes can chain.
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    if node_type == "videoGen" and output_url:
        try:
            from app.services.node_runner import NodeRunner
            runner = NodeRunner()
            start_frame = runner._extract_video_frame(output_url, "start_frame")
            end_frame = runner._extract_video_frame(output_url, "end_frame")
        except Exception as e:
            logger.warning("[FalWebhook] frame extraction failed: %s", e)

    now = datetime.now(timezone.utc)

    # ── Branch A: Run-All job mode ───────────────────────────────────────────
    if job_id and task_index is not None:
        jobs = get_workflow_jobs_collection()
        workflows = get_workflows_collection()

        set_fields = {
            f"tasks.{task_index}.status": "completed",
            f"tasks.{task_index}.completed_at": now.isoformat(),
            f"outputs.{node_id}": output_url,
            "updated_at": now,
            "heartbeat_at": now,
        }
        if start_frame:
            set_fields[f"outputs.{node_id}__start_frame"] = start_frame
        if end_frame:
            set_fields[f"outputs.{node_id}__end_frame"] = end_frame
        await jobs.update_one({"id": job_id}, {"$set": set_fields})

        # Mirror into workflow.outputs
        try:
            from bson import ObjectId

            wf_oid = ObjectId(workflow_id) if workflow_id else None
            if wf_oid:
                wf_set = {f"outputs.{node_id}": output_url, "updated_at": now}
                if start_frame:
                    wf_set[f"outputs.{node_id}__start_frame"] = start_frame
                if end_frame:
                    wf_set[f"outputs.{node_id}__end_frame"] = end_frame
                await workflows.update_one({"_id": wf_oid}, {"$set": wf_set})
        except Exception as e:
            logger.warning("[FalWebhook] workflow output mirror failed: %s", e)

        await _charge_billing(
            cost_usd, node_type, user_id, model_name, provider,
            workflow_id, node_id, billing_meta,
        )

        # Chain the next task
        try:
            from app.api.endpoints.workflow import _invoke_job_processor_lambda
            await _invoke_job_processor_lambda(job_id)
        except Exception as e:
            logger.warning("[FalWebhook] job-processor re-invoke failed: %s", e)
        return

    # ── Branch B: Single-node async run mode ─────────────────────────────────
    if not run_id:
        logger.warning(
            "[FalWebhook] context missing job_id and run_id — skipping: %s", ctx,
        )
        return

    workflows = get_workflows_collection()
    try:
        from bson import ObjectId
        wf_oid = ObjectId(workflow_id)
    except Exception:
        logger.warning("[FalWebhook] invalid workflow_id in ctx: %s", workflow_id)
        return

    wf_set: dict = {
        f"execution.node_states.{node_id}.status": "completed",
        f"execution.node_states.{node_id}.completed_at": now.isoformat(),
        f"execution.node_states.{node_id}.error": None,
        f"execution.outputs.{node_id}": output_url,
        f"outputs.{node_id}": output_url,
        "execution.status": "completed",
        "updated_at": now,
    }
    if start_frame:
        wf_set[f"outputs.{node_id}__start_frame"] = start_frame
        wf_set[f"execution.outputs.{node_id}__start_frame"] = start_frame
    if end_frame:
        wf_set[f"outputs.{node_id}__end_frame"] = end_frame
        wf_set[f"execution.outputs.{node_id}__end_frame"] = end_frame

    await workflows.update_one({"_id": wf_oid}, {"$set": wf_set})

    # Register asset in persistent user_assets collection so the asset sidebar picks it up.
    try:
        from app.api.endpoints.user_assets import _is_media_url, register_asset
        if output_url and isinstance(output_url, str) and _is_media_url(output_url):
            workflow_doc = await workflows.find_one({"_id": wf_oid}, {"name": 1, "nodes": 1})
            wf_name = (workflow_doc or {}).get("name", "Untitled Workflow")
            target_node = next(
                (n for n in (workflow_doc or {}).get("nodes", []) if n.get("id") == node_id),
                None,
            )
            await register_asset(
                user_id=user_id,
                workflow_id=workflow_id,
                workflow_name=wf_name,
                node_id=node_id,
                node_type=node_type or "",
                asset_url=output_url,
                node_data=(target_node or {}).get("data"),
            )
    except Exception as reg_err:
        logger.warning("[FalWebhook] asset registration failed: %s", reg_err)

    await _charge_billing(
        cost_usd, node_type, user_id, model_name, provider,
        workflow_id, node_id, billing_meta,
    )

    logger.info(
        "[FalWebhook] single-node run finalized: workflow=%s node=%s run_id=%s",
        workflow_id, node_id, run_id,
    )


async def _charge_billing(
    cost_usd: float,
    node_type: Optional[str],
    user_id: Optional[str],
    model_name: str,
    provider: str,
    workflow_id: Optional[str],
    node_id: Optional[str],
    billing_meta: Optional[dict] = None,
) -> None:
    if not node_type or node_type not in _ACTION_TYPE_MAP or not user_id:
        return
    if cost_usd <= 0:
        logger.warning(
            "[FalWebhook] billable run completed with cost_usd=0 — skipping "
            "usage_logs insert. node_type=%s model=%s workflow=%s node=%s meta=%s. "
            "Check fal_pricing fallback chain for this endpoint.",
            node_type, model_name, workflow_id, node_id, billing_meta,
        )
        return
    try:
        billing = BillingService(get_database())
        metadata: dict = {
            "workflow_id": workflow_id,
            "node_id": node_id,
            "node_type": node_type,
        }
        if billing_meta:
            # Keep fal audit fields alongside the charge for reconciliation.
            metadata.update({k: v for k, v in billing_meta.items() if v is not None})
        await billing.charge_usage(
            user_id=user_id,
            action=_ACTION_TYPE_MAP[node_type],
            cost_usd=cost_usd,
            model_name=model_name,
            provider=provider,
            metadata=metadata,
        )
    except Exception as e:
        logger.warning("[FalWebhook] billing failed: %s", e)


async def _write_task_failure(ctx: dict, error: str) -> None:
    job_id = ctx.get("job_id")
    task_index = ctx.get("task_index")
    run_id = ctx.get("run_id")
    node_id = ctx.get("node_id")
    workflow_id = ctx.get("workflow_id")
    now = datetime.now(timezone.utc)

    # Run-All job mode
    if job_id and task_index is not None:
        jobs = get_workflow_jobs_collection()
        await jobs.update_one(
            {"id": job_id},
            {
                "$set": {
                    f"tasks.{task_index}.status": "failed",
                    f"tasks.{task_index}.completed_at": now.isoformat(),
                    f"tasks.{task_index}.error": error,
                    "status": "failed",
                    "updated_at": now,
                    "heartbeat_at": now,
                },
                "$push": {"errors": {"node_id": node_id, "error": error}},
            },
        )
        return

    # Single-node async run mode
    if not (run_id and node_id and workflow_id):
        return
    try:
        from bson import ObjectId
        wf_oid = ObjectId(workflow_id)
    except Exception:
        return

    workflows = get_workflows_collection()
    await workflows.update_one(
        {"_id": wf_oid},
        {"$set": {
            f"execution.node_states.{node_id}.status": "failed",
            f"execution.node_states.{node_id}.completed_at": now.isoformat(),
            f"execution.node_states.{node_id}.error": error,
            "execution.status": "failed",
            "updated_at": now,
        }},
    )
