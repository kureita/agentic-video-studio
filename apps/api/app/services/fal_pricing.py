"""
FalPricingService — dynamic fal.ai pricing with 24h MongoDB cache.

Flow:
  1. Live cost = (billable_units | estimated_units) × unit_price_from_fal
  2. Unit price is fetched from fal's Platform API (GET /v1/models/pricing) and
     cached in the `fal_pricing` collection. Refreshed opportunistically when the
     cache entry is older than 24h or absent.
  3. On any failure (network, 5xx, stale data, missing model) we fall back to the
     registry's `fallback_price`.
  4. Never charges for failed runs — call sites only invoke `charge_for_run` after
     the fal webhook reports a successful result.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.model_registry import get_model_by_endpoint_id

logger = logging.getLogger(__name__)

_PRICING_API = "https://api.fal.ai/v1/models/pricing"
_CACHE_TTL = timedelta(days=1)
_HTTP_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


class FalPricingService:
    """Resolve live fal.ai unit prices + compute run cost, backed by a 24h cache."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.fal_pricing

    # ------------------------------------------------------------------
    # Unit price resolution
    # ------------------------------------------------------------------
    async def get_unit_price(self, endpoint_id: str) -> dict[str, Any]:
        """Return `{unit_price, unit, currency, source}` for *endpoint_id*.

        `source` is one of: "cache", "live", "fallback".
        """
        now = datetime.now(timezone.utc)

        cached = await self.collection.find_one({"endpoint_id": endpoint_id})
        if cached:
            last_checked = cached.get("last_checked_at")
            if isinstance(last_checked, datetime) and (now - last_checked) < _CACHE_TTL:
                return {
                    "unit_price": cached["unit_price"],
                    "unit": cached["unit"],
                    "currency": cached.get("currency", "USD"),
                    "source": "cache",
                }

        # Try live refresh
        live = await self._fetch_live_price(endpoint_id)
        if live is not None:
            await self.collection.update_one(
                {"endpoint_id": endpoint_id},
                {"$set": {**live, "last_checked_at": now}},
                upsert=True,
            )
            return {**live, "source": "live"}

        # Cached-but-stale is better than nothing
        if cached:
            return {
                "unit_price": cached["unit_price"],
                "unit": cached["unit"],
                "currency": cached.get("currency", "USD"),
                "source": "cache",
            }

        # Last-resort fallback from registry
        model = get_model_by_endpoint_id(endpoint_id) or {}
        fp: dict[str, Any] = model.get("fallback_price") or {}
        if "per_run" in fp:
            return {"unit_price": float(fp["per_run"]), "unit": "run",
                    "currency": "USD", "source": "fallback"}
        if "per_second" in fp:
            return {"unit_price": float(fp["per_second"]), "unit": "seconds",
                    "currency": "USD", "source": "fallback"}
        if "per_min" in fp:
            return {"unit_price": float(fp["per_min"]) / 60.0, "unit": "seconds",
                    "currency": "USD", "source": "fallback"}
        if "per_1k_chars" in fp:
            return {"unit_price": float(fp["per_1k_chars"]) / 1000.0, "unit": "character",
                    "currency": "USD", "source": "fallback"}

        logger.warning("[FalPricing] No pricing available for %s — charging 0", endpoint_id)
        return {"unit_price": 0.0, "unit": "run", "currency": "USD", "source": "fallback"}

    async def _fetch_live_price(self, endpoint_id: str) -> Optional[dict[str, Any]]:
        api_key = settings.fal_api_key
        if not api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.get(
                    _PRICING_API,
                    params={"endpoint_id": endpoint_id},
                    headers={"Authorization": f"Key {api_key}"},
                )
            if resp.status_code != 200:
                logger.warning(
                    "[FalPricing] live price %s → HTTP %s", endpoint_id, resp.status_code
                )
                return None
            data = resp.json() or {}
            for price in data.get("prices", []):
                if price.get("endpoint_id") == endpoint_id:
                    return {
                        "endpoint_id": endpoint_id,
                        "unit_price": float(price["unit_price"]),
                        "unit": str(price["unit"]),
                        "currency": price.get("currency", "USD"),
                    }
            return None
        except Exception as e:
            logger.warning("[FalPricing] live price fetch failed for %s: %s", endpoint_id, e)
            return None

    # ------------------------------------------------------------------
    # Cost computation
    # ------------------------------------------------------------------
    async def compute_cost_usd(
        self,
        endpoint_id: str,
        *,
        billable_units: Optional[float] = None,
        duration_s: Optional[float] = None,
        chars: Optional[int] = None,
    ) -> dict[str, Any]:
        """Compute USD cost for a completed run.

        Authoritative path (used in production via the fal webhook):
          * `billable_units` is pulled from the `X-Fal-Billable-Units` response
            header on fal's queue result endpoint. When provided, cost is
            `billable_units × unit_price` — this is exactly how fal bills us,
            so we match it byte-for-byte regardless of the unit label
            ("image", "units", "1000 tokens", "compute seconds", ...).

        Estimation path (fallback only — used in sync/dev mode where we don't
        pull the response headers):
          * Derived from `duration_s` / `chars` based on the model's billing
            unit string. Errors here are small for video models that bill per
            second, but will dramatically under-charge for token/compute-unit
            models. Avoid whenever possible.

        If no unit count is resolvable, defaults to 1 unit (per-run pricing).
        """
        price = await self.get_unit_price(endpoint_id)
        unit_label = price["unit"]
        unit = unit_label.lower()
        unit_price = float(price["unit_price"])

        resolution: str
        if billable_units is not None:
            units = float(billable_units)
            resolution = "billable_units"
        elif unit in ("second", "seconds") and duration_s is not None:
            units = float(duration_s)
            resolution = "duration_s"
        elif unit in ("character", "characters") and chars is not None:
            units = float(chars)
            resolution = "chars"
        elif unit in ("1k_characters", "thousand_characters") and chars is not None:
            units = float(chars) / 1000.0
            resolution = "chars/1000"
        elif unit in ("minute", "minutes") and duration_s is not None:
            units = float(duration_s) / 60.0
            resolution = "duration_s/60"
        else:
            # Unknown unit (e.g. "units", "1000 tokens", "compute seconds", "megapixel")
            # and no billable_units from fal — we can't estimate reliably. Log so we
            # notice, then fall through to per-run pricing.
            units = 1.0
            resolution = "per_run_fallback"
            if billable_units is None:
                logger.warning(
                    "[FalPricing] no billable_units for %s (unit=%r) — charging 1 "
                    "unit × $%.6f. This will under-charge token/compute-unit "
                    "models; fetch X-Fal-Billable-Units instead.",
                    endpoint_id, unit_label, unit_price,
                )

        cost_usd = round(unit_price * units, 6)
        return {
            "cost_usd": cost_usd,
            "unit_price": unit_price,
            "unit": unit_label,
            "units": units,
            "source": price["source"],
            "resolution": resolution,
        }


def extract_billable_units(headers_or_meta: Any) -> Optional[float]:
    """Extract `X-Fal-Billable-Units` from any dict-like headers/meta, tolerant of case."""
    if not headers_or_meta:
        return None
    try:
        for key in (
            "X-Fal-Billable-Units",
            "x-fal-billable-units",
            "billable_units",
            "X-Billable-Units",
        ):
            v = headers_or_meta.get(key) if hasattr(headers_or_meta, "get") else None
            if v is not None:
                return float(v)
    except (TypeError, ValueError):
        pass
    return None
