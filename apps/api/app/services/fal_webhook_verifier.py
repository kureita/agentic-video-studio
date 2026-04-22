"""
Fal.ai webhook signature verifier.

Verifies ED25519 signatures using JWKS fetched from
`https://rest.fal.ai/.well-known/jwks.json`. Cached in-memory for up to 24h.

Reference: https://fal.ai/docs/model-endpoints/webhooks#verifying-your-webhook
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import time
from typing import Any

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

logger = logging.getLogger(__name__)

JWKS_URL = "https://rest.fal.ai/.well-known/jwks.json"
_JWKS_CACHE_TTL_S = 24 * 60 * 60
_TIMESTAMP_LEEWAY_S = 300  # ±5 min

_jwks_cache: list[dict[str, Any]] | None = None
_jwks_cache_time: float = 0.0
_jwks_lock = asyncio.Lock()


async def _fetch_jwks(force: bool = False) -> list[dict[str, Any]]:
    """Fetch JWKS with 24h in-memory cache."""
    global _jwks_cache, _jwks_cache_time
    now = time.time()
    if not force and _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_CACHE_TTL_S:
        return _jwks_cache

    async with _jwks_lock:
        # double-check after acquiring lock
        now = time.time()
        if not force and _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_CACHE_TTL_S:
            return _jwks_cache

        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            resp = await client.get(JWKS_URL)
            resp.raise_for_status()
        _jwks_cache = (resp.json() or {}).get("keys", []) or []
        _jwks_cache_time = time.time()
        return _jwks_cache


async def verify_webhook_signature(
    *,
    request_id: str,
    user_id: str,
    timestamp: str,
    signature_hex: str,
    body: bytes,
) -> bool:
    """Verify a fal.ai webhook signature.

    Returns True iff all of these hold:
      - Timestamp within ±5 min of server clock
      - Signature hex-decodable
      - At least one JWKS key successfully verifies the ED25519 signature of
        `"{request_id}\\n{user_id}\\n{timestamp}\\n{sha256_hex(body)}"`
    """
    if not all([request_id, user_id, timestamp, signature_hex]):
        return False

    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        logger.warning("[FalWebhook] bad timestamp format: %r", timestamp)
        return False
    if abs(int(time.time()) - ts) > _TIMESTAMP_LEEWAY_S:
        logger.warning("[FalWebhook] timestamp outside leeway: %s", ts)
        return False

    try:
        signature_bytes = bytes.fromhex(signature_hex)
    except ValueError:
        logger.warning("[FalWebhook] signature not hex: %r", signature_hex[:32])
        return False

    body_hash = hashlib.sha256(body).hexdigest()
    message = "\n".join([request_id, user_id, timestamp, body_hash]).encode("utf-8")

    def _try_keys(keys: list[dict[str, Any]]) -> bool:
        for key in keys:
            x = key.get("x")
            if not isinstance(x, str):
                continue
            try:
                pad = "=" * (-len(x) % 4)
                public_key_bytes = base64.urlsafe_b64decode(x + pad)
                VerifyKey(public_key_bytes).verify(message, signature_bytes)
                return True
            except BadSignatureError:
                continue
            except Exception as e:
                logger.debug("[FalWebhook] key verify error: %s", e)
                continue
        return False

    # First try cached JWKS; if no key matches, force-refresh and retry once
    if _try_keys(await _fetch_jwks()):
        return True
    return _try_keys(await _fetch_jwks(force=True))
