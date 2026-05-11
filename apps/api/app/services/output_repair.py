"""Detect and repair workflow video outputs that were uploaded to S3 with the
wrong file extension.

The original `_download_and_upload` bug saved video bytes as `*.mp3` for
capabilities like reference / elements / v2v. That breaks the browser:
auto-extract loads the URL into a `<video crossOrigin="anonymous">` element,
S3 has no CORS header, and the request is denied — every page load floods
the console with errors and the per-handle "Generate Preview" button never
works.

This module is the shared core used by:
  * `scripts/fix_mislabeled_video_outputs.py` (one-shot bulk repair)
  * `/api/workflows/{id}/reconcile-fal-jobs` (auto-runs on workflow load)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


_VIDEO_NODE_TYPES = frozenset({"videoGen", "editorAgent"})


def is_signed_s3_video_with_audio_ext(url: Any) -> bool:
    """True if `url` looks like our S3 + has an audio path extension.

    Signed query strings are stripped before the check so the rotating
    `?X-Amz-Signature=...` doesn't matter.
    """
    if not isinstance(url, str):
        return False
    if "kureita.s3" not in url:
        return False
    path = url.split("?", 1)[0].lower()
    return path.endswith(".mp3")


def bucket_key_from_url(url: str) -> Optional[str]:
    """Pull just the S3 object key out of a full HTTPS URL."""
    m = re.match(r"https://[^/]+/(?P<key>[^?]+)", url)
    return m.group("key") if m else None


def _new_mp4_key(old_key: str) -> str:
    base = old_key[:-4] if old_key.lower().endswith(".mp3") else old_key
    suffix = f"_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
    return f"{base}{suffix}"


async def repair_workflow_outputs(
    workflow: dict,
    *,
    db,
    s3_client,
    bucket: str,
    region: str,
    delete_old: bool = False,
) -> dict[str, Any]:
    """Repair every mislabeled `.mp3` video output on one workflow doc.

    Returns `{"scanned": N, "repaired": M, "errors": [..]}` so callers can
    surface progress to the user.

    The S3 server-side copy is idempotent — rerunning is safe; if no bad
    outputs are found, nothing happens.
    """
    workflows = db.workflows
    workflow_jobs = db.workflow_jobs
    fal_jobs = db.fal_jobs
    user_assets = db.user_assets

    wf_id = workflow.get("_id")
    wf_id_str = str(wf_id)
    nodes = {n.get("id"): n for n in (workflow.get("nodes") or [])}
    outputs = workflow.get("outputs") or {}

    scanned = 0
    repaired = 0
    errors: list[str] = []

    loop = asyncio.get_event_loop()

    for node_id, url in list(outputs.items()):
        # Skip frame thumbnail keys like `<id>__start_frame`.
        if "__" in node_id:
            continue
        if not is_signed_s3_video_with_audio_ext(url):
            continue
        node = nodes.get(node_id) or {}
        if node.get("type") not in _VIDEO_NODE_TYPES:
            continue

        scanned += 1
        old_key = bucket_key_from_url(url)
        if not old_key:
            errors.append(f"node={node_id}: could not parse S3 key from {url!r}")
            continue

        new_key = _new_mp4_key(old_key)
        try:
            await loop.run_in_executor(
                None,
                lambda old=old_key, new=new_key: s3_client.copy_object(
                    Bucket=bucket,
                    CopySource={"Bucket": bucket, "Key": old},
                    Key=new,
                    ContentType="video/mp4",
                    MetadataDirective="REPLACE",
                ),
            )
        except Exception as e:
            errors.append(f"node={node_id}: S3 copy failed ({e})")
            logger.warning(
                "[output-repair] copy failed wf=%s node=%s old=%s err=%s",
                wf_id_str, node_id, old_key, e,
            )
            continue

        new_url = f"https://{bucket}.s3.{region}.amazonaws.com/{new_key}"

        # Rewrite every reference. Order doesn't matter — workflows.outputs is
        # the canonical one for the UI, the rest are for API consistency.
        try:
            await workflows.update_one(
                {"_id": wf_id},
                {"$set": {f"outputs.{node_id}": new_url}},
            )
            for n in (workflow.get("nodes") or []):
                if n.get("id") == node_id and (n.get("data") or {}).get("output"):
                    await workflows.update_one(
                        {"_id": wf_id, "nodes.id": node_id},
                        {"$set": {"nodes.$.data.output": new_url}},
                    )
            await workflow_jobs.update_many(
                {"id": wf_id_str, f"outputs.{node_id}": {"$exists": True}},
                {"$set": {f"outputs.{node_id}": new_url}},
            )
            await fal_jobs.update_many(
                {"context.workflow_id": wf_id_str, "context.node_id": node_id},
                {"$set": {"output_url": new_url}},
            )
            await user_assets.update_many(
                {"workflow_id": wf_id_str, "node_id": node_id, "url": {"$regex": r"\.mp3"}},
                {"$set": {"url": new_url}},
            )
        except Exception as e:
            errors.append(f"node={node_id}: mongo update failed ({e})")
            logger.warning(
                "[output-repair] mongo update failed wf=%s node=%s err=%s",
                wf_id_str, node_id, e,
            )
            continue

        if delete_old:
            try:
                await loop.run_in_executor(
                    None,
                    lambda old=old_key: s3_client.delete_object(Bucket=bucket, Key=old),
                )
            except Exception as e:
                logger.warning(
                    "[output-repair] delete old key failed wf=%s key=%s err=%s",
                    wf_id_str, old_key, e,
                )

        # Mutate the in-memory workflow dict so subsequent passes (or callers
        # who reuse this doc) see the new URL too.
        workflow.setdefault("outputs", {})[node_id] = new_url

        repaired += 1
        logger.info(
            "[output-repair] wf=%s node=%s renamed %s -> %s",
            wf_id_str, node_id, old_key, new_key,
        )

    return {"scanned": scanned, "repaired": repaired, "errors": errors}


def build_s3_client():
    """Construct a boto3 S3 client from settings. Imported lazily so callers
    that don't actually need S3 (like the import sweep) don't pay for it.
    """
    import boto3  # type: ignore

    from app.core.config import settings

    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if getattr(settings, "s3_endpoint", ""):
        kwargs["endpoint_url"] = settings.s3_endpoint
    return boto3.client("s3", **kwargs)
