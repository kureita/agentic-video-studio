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
import math
import re
from copy import deepcopy
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
            # Mongo round-trips drop tzinfo on some driver versions — coerce
            # back to UTC so we don't trip the offset-naive vs offset-aware
            # subtraction guard.
            if isinstance(last_checked, datetime) and last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)
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

        return _fallback_unit_price(endpoint_id)

    async def get_unit_prices(self, endpoint_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Batch resolve unit prices for endpoint IDs.

        fal's pricing API accepts up to 50 endpoint IDs per request; the model
        catalog is small enough to refresh in one call while still honoring the
        same 24h Mongo cache used by `get_unit_price`.
        """
        now = datetime.now(timezone.utc)
        unique_ids = list(dict.fromkeys(e for e in endpoint_ids if e))
        resolved: dict[str, dict[str, Any]] = {}

        if not unique_ids:
            return resolved

        cursor = self.collection.find({"endpoint_id": {"$in": unique_ids}})
        async for cached in cursor:
            endpoint_id = cached.get("endpoint_id")
            last_checked = cached.get("last_checked_at")
            if isinstance(last_checked, datetime) and last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)
            if endpoint_id and isinstance(last_checked, datetime) and (now - last_checked) < _CACHE_TTL:
                resolved[endpoint_id] = {
                    "unit_price": cached["unit_price"],
                    "unit": cached["unit"],
                    "currency": cached.get("currency", "USD"),
                    "source": "cache",
                }

        missing = [endpoint_id for endpoint_id in unique_ids if endpoint_id not in resolved]
        if missing:
            live = await self._fetch_live_prices(missing)
            for endpoint_id, price in live.items():
                await self.collection.update_one(
                    {"endpoint_id": endpoint_id},
                    {"$set": {**price, "last_checked_at": now}},
                    upsert=True,
                )
                resolved[endpoint_id] = {**price, "source": "live"}

        for endpoint_id in unique_ids:
            if endpoint_id not in resolved:
                resolved[endpoint_id] = _fallback_unit_price(endpoint_id)

        return resolved

    async def _fetch_live_price(self, endpoint_id: str) -> Optional[dict[str, Any]]:
        prices = await self._fetch_live_prices([endpoint_id])
        return prices.get(endpoint_id)

    async def _fetch_live_prices(self, endpoint_ids: list[str]) -> dict[str, dict[str, Any]]:
        api_key = settings.fal_api_key
        if not api_key:
            return {}
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.get(
                    _PRICING_API,
                    params={"endpoint_id": ",".join(endpoint_ids)},
                    headers={"Authorization": f"Key {api_key}"},
                )
            if resp.status_code != 200:
                logger.warning(
                    "[FalPricing] live price batch (%s endpoints) → HTTP %s",
                    len(endpoint_ids), resp.status_code,
                )
                return {}
            data = resp.json() or {}
            prices: dict[str, dict[str, Any]] = {}
            for price in data.get("prices", []):
                endpoint_id = price.get("endpoint_id")
                if endpoint_id in endpoint_ids:
                    prices[endpoint_id] = {
                        "endpoint_id": endpoint_id,
                        "unit_price": float(price["unit_price"]),
                        "unit": str(price["unit"]),
                        "currency": price.get("currency", "USD"),
                    }
            return prices
        except Exception as e:
            logger.warning(
                "[FalPricing] live price batch fetch failed for %s endpoints: %s",
                len(endpoint_ids), e,
            )
            return {}

    # ------------------------------------------------------------------
    # Catalog estimates
    # ------------------------------------------------------------------
    async def enrich_models_for_user_estimates(
        self,
        models: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return model catalog copy with live fal-based user estimates.

        `est_provider_price_usd` is the raw fal/provider estimate.
        `est_price_usd` is the user-facing estimate including Kureita commission.

        Final billing does not use these fields; webhook/sync completion paths
        charge from actual fal cost metadata and BillingService adds commission.
        """
        enriched = deepcopy(models)
        prices = await self.get_unit_prices([
            str(model.get("model_endpoint_id"))
            for model in enriched
            if model.get("model_endpoint_id")
        ])

        for model in enriched:
            endpoint_id = model.get("model_endpoint_id")
            if not endpoint_id:
                continue

            price = prices.get(str(endpoint_id))

            configs = model.get("configs") or []
            for cfg in configs:
                provider_estimate = None
                estimate_source = "registry"

                if price:
                    provider_estimate = _estimate_config_provider_cost(cfg, price, model)
                    if provider_estimate is not None:
                        estimate_source = price.get("source", "live")
                        cfg["fal_endpoint_id"] = endpoint_id
                        cfg["fal_unit"] = price.get("unit")
                        cfg["fal_unit_price_usd"] = float(price.get("unit_price") or 0.0)
                        cfg["fal_price_source"] = price.get("source")

                if provider_estimate is None:
                    provider_estimate = _registry_config_provider_cost(cfg, model)

                if provider_estimate is not None:
                    cfg["est_provider_price_usd"] = round(float(provider_estimate), 6)
                    cfg["est_price_usd"] = _with_commission(provider_estimate)
                    cfg["est_price_source"] = estimate_source

                provider_per_min, per_min_source = _config_provider_per_min(cfg, price, model)
                if provider_per_min is not None:
                    cfg["est_provider_price_usd_per_min"] = round(float(provider_per_min), 6)
                    cfg["est_price_usd_per_min"] = _with_commission(provider_per_min)
                    cfg["est_price_source"] = per_min_source or estimate_source

                provider_per_second, per_second_source = _config_provider_per_second(cfg, price, model)
                if provider_per_second is not None:
                    cfg["est_provider_price_usd_per_second"] = round(float(provider_per_second), 6)
                    cfg["est_price_usd_per_second"] = _with_commission(provider_per_second)
                    cfg["est_price_source"] = per_second_source or estimate_source

        return enriched

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
        resolution_label: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
    ) -> dict[str, Any]:
        """Compute USD cost for a completed run.

        Order of preference (most → least authoritative):
          1. `billable_units × unit_price` — both pulled from fal. Matches
             fal's invoice byte-for-byte.
          2. `unit_price × derived_units` for natural unit labels
             (seconds/characters/minutes) when we have the corresponding
             input metadata.
          3. **Config-matched estimate** — find the model registry entry for
             this endpoint, locate the config whose (resolution, duration)
             matches what was requested, and use its `est_price_usd`. This
             is far more accurate than per_run for resolution/duration-priced
             models and is the right fallback when fal's billable_units
             header is unavailable.
          4. `fallback_price.per_run` from the registry.
          5. Zero. Logs loudly because this means the user wasn't charged.
        """
        price = await self.get_unit_price(endpoint_id)
        unit_label = price["unit"]
        unit = unit_label.lower()
        unit_price = float(price["unit_price"])
        price_source = price["source"]

        # The registry per_run fallback is NOT a per-unit price — it's a
        # whole-run dollar amount. If we got it because fal's live pricing API
        # was down, we must not multiply it by billable_units (would charge
        # billable_units × $per_run, which can be 10× the real charge for
        # second-billed video models). Fall through to the config-matched
        # estimate instead.
        per_unit_pricing_trustworthy = price_source in ("cache", "live")

        # 1 + 2 — multiply unit_price by an authoritative or natural-unit count.
        units: Optional[float] = None
        resolution_source: Optional[str] = None
        if per_unit_pricing_trustworthy:
            if billable_units is not None:
                units = float(billable_units)
                resolution_source = "billable_units"
            elif unit in ("second", "seconds") and duration_s is not None:
                units = float(duration_s)
                resolution_source = "duration_s"
            elif unit in ("character", "characters") and chars is not None:
                units = float(chars)
                resolution_source = "chars"
            elif unit in ("1k_characters", "thousand_characters") and chars is not None:
                units = float(chars) / 1000.0
                resolution_source = "chars/1000"
            elif unit in ("minute", "minutes") and duration_s is not None:
                # Per-minute providers (e.g. ElevenLabs Music on fal) round up
                # to the closest minute when invoicing. Estimate the same way
                # so a 30s clip bills at 1 minute, not 0.5.
                units = float(math.ceil(float(duration_s) / 60.0))
                resolution_source = "duration_s/60_ceil"

        if units is not None:
            cost_usd = round(unit_price * units, 6)

            # Sanity check: fal's pricing API and queue header don't always
            # agree on what "1 unit" means (some models price per token, some
            # per second, some per compute-unit). When `units × unit_price`
            # comes out wildly different from what the model registry config
            # says this run should cost, the math is almost certainly wrong —
            # prefer the registry estimate rather than under/over-charging by
            # 10–100×. Bounds are deliberately loose (0.25× / 4×) so genuine
            # variance doesn't trigger a swap.
            sanity = _registry_sanity_estimate(
                endpoint_id, resolution_label, duration_s, aspect_ratio,
            )
            if sanity is not None and sanity > 0:
                ratio = cost_usd / sanity if sanity else 0
                if cost_usd < sanity * 0.25 or cost_usd > sanity * 4.0:
                    logger.warning(
                        "[FalPricing] %s computed cost $%.4f is %.2fx the "
                        "registry estimate $%.4f (units=%s × unit_price=$%s). "
                        "Pricing data likely mis-aligned (unit label mismatch?). "
                        "Falling back to registry estimate.",
                        endpoint_id, cost_usd, ratio, sanity,
                        units, unit_price,
                    )
                    return {
                        "cost_usd": round(sanity, 6),
                        "unit_price": float(sanity),
                        "unit": "run",
                        "units": 1.0,
                        "source": "registry_sanity_clamp",
                        "resolution": f"{resolution_source}->clamped",
                    }

            return {
                "cost_usd": cost_usd,
                "unit_price": unit_price,
                "unit": unit_label,
                "units": units,
                "source": price_source,
                "resolution": resolution_source,
            }

        # 3 — config-matched estimate. For models priced per resolution+duration
        # (most video models), this is much closer to fal's actual charge than
        # the per_run fallback.
        model = get_model_by_endpoint_id(endpoint_id) or {}
        configs = model.get("configs") or []
        if configs:
            matched_config = _match_config(configs, resolution_label, duration_s, aspect_ratio)
            if matched_config is not None:
                est = matched_config.get("est_price_usd")
                if isinstance(est, (int, float)) and est > 0:
                    logger.info(
                        "[FalPricing] no billable_units for %s — using config "
                        "est_price_usd=%.4f (config=%s, res=%r, dur=%r)",
                        endpoint_id, est, matched_config.get("id"),
                        resolution_label, duration_s,
                    )
                    return {
                        "cost_usd": round(float(est), 6),
                        "unit_price": float(est),
                        "unit": "run",
                        "units": 1.0,
                        "source": "registry_config_estimate",
                        "resolution": f"config:{matched_config.get('id')}",
                    }

        # 4 — registry per_run fallback. Better than zero but coarse.
        fp = model.get("fallback_price") or {}
        if "per_run" in fp:
            per_run = float(fp["per_run"])
            logger.warning(
                "[FalPricing] no billable_units and no matching config for %s — "
                "using fallback per_run=$%.4f. This may under/over-charge.",
                endpoint_id, per_run,
            )
            return {
                "cost_usd": round(per_run, 6),
                "unit_price": per_run,
                "unit": "run",
                "units": 1.0,
                "source": "registry_per_run_fallback",
                "resolution": "per_run_fallback",
            }

        # 5 — last resort. Don't silently charge bad numbers.
        logger.error(
            "[FalPricing] cannot resolve cost for %s — billing $0 (unit=%r, "
            "unit_price=%.6f). User will not be charged for this run; "
            "investigate the registry entry.",
            endpoint_id, unit_label, unit_price,
        )
        return {
            "cost_usd": 0.0,
            "unit_price": unit_price,
            "unit": unit_label,
            "units": 0.0,
            "source": price["source"],
            "resolution": "unresolved",
        }


def _registry_sanity_estimate(
    endpoint_id: str,
    resolution_label: Optional[str],
    duration_s: Optional[float],
    aspect_ratio: Optional[str],
) -> Optional[float]:
    """Best-guess registry price for this run, used purely as a sanity bound.

    Tries config-matched `est_price_usd` first, then `fallback_price.per_run`.
    Returns None when the registry has nothing useful to compare against —
    callers should NOT clamp in that case.
    """
    model = get_model_by_endpoint_id(endpoint_id) or {}
    configs = model.get("configs") or []
    matched = _match_config(configs, resolution_label, duration_s, aspect_ratio)
    if matched is not None:
        est = matched.get("est_price_usd")
        if isinstance(est, (int, float)) and est > 0:
            return float(est)
    fp = model.get("fallback_price") or {}
    per_run = fp.get("per_run")
    if isinstance(per_run, (int, float)) and per_run > 0:
        return float(per_run)
    return None


def _fallback_unit_price(endpoint_id: str) -> dict[str, Any]:
    model = get_model_by_endpoint_id(endpoint_id) or {}
    fp: dict[str, Any] = model.get("fallback_price") or {}
    if "per_run" in fp:
        return {
            "unit_price": float(fp["per_run"]),
            "unit": "run",
            "currency": "USD",
            "source": "fallback",
        }
    if "per_second" in fp:
        return {
            "unit_price": float(fp["per_second"]),
            "unit": "seconds",
            "currency": "USD",
            "source": "fallback",
        }
    if "per_min" in fp:
        return {
            "unit_price": float(fp["per_min"]) / 60.0,
            "unit": "seconds",
            "currency": "USD",
            "source": "fallback",
        }
    if "per_1k_chars" in fp:
        return {
            "unit_price": float(fp["per_1k_chars"]) / 1000.0,
            "unit": "character",
            "currency": "USD",
            "source": "fallback",
        }

    logger.warning("[FalPricing] No pricing available for %s — charging 0", endpoint_id)
    return {"unit_price": 0.0, "unit": "run", "currency": "USD", "source": "fallback"}


def _match_config(
    configs: list[dict[str, Any]],
    resolution_label: Optional[str],
    duration_s: Optional[float],
    aspect_ratio: Optional[str],
) -> Optional[dict[str, Any]]:
    """Find the registry config that best matches the user's request.

    Match priority:
      1. Exact (resolution, duration) match.
      2. Same duration if resolution unknown.
      3. Same resolution if duration unknown.
      4. None — caller falls back to per_run.

    `aspect_ratio` is consulted only as a tiebreaker because most fal models
    price by (resolution, duration) and ignore aspect ratio.
    """
    if not configs:
        return None

    res_norm = (resolution_label or "").strip().lower() or None
    dur_int = int(duration_s) if isinstance(duration_s, (int, float)) and duration_s > 0 else None

    def candidates(filter_fn: Any) -> list[dict[str, Any]]:
        return [c for c in configs if filter_fn(c)]

    if res_norm and dur_int is not None:
        exact = candidates(
            lambda c: str(c.get("resolution", "")).lower() == res_norm
            and int(c.get("duration", -1) or -1) == dur_int
        )
        if exact:
            return _tie_break_by_aspect(exact, aspect_ratio)

    if dur_int is not None:
        dur_only = candidates(lambda c: int(c.get("duration", -1) or -1) == dur_int)
        if dur_only:
            return _tie_break_by_aspect(dur_only, aspect_ratio)

    if res_norm:
        res_only = candidates(lambda c: str(c.get("resolution", "")).lower() == res_norm)
        if res_only:
            return _tie_break_by_aspect(res_only, aspect_ratio)

    return None


def _tie_break_by_aspect(
    configs: list[dict[str, Any]], aspect_ratio: Optional[str]
) -> dict[str, Any]:
    if not aspect_ratio:
        return configs[0]
    ar = aspect_ratio.strip()
    for c in configs:
        ratios = c.get("aspect_ratios") or []
        if ar in ratios:
            return c
    return configs[0]


def _with_commission(provider_cost: float) -> float:
    return round(float(provider_cost) * (1.0 + float(settings.commission_multiplier)), 6)


def _registry_config_provider_cost(
    cfg: dict[str, Any],
    model: dict[str, Any],
) -> Optional[float]:
    est = cfg.get("est_provider_price_usd")
    if isinstance(est, (int, float)) and est > 0:
        return float(est)

    est = cfg.get("est_price_usd")
    if isinstance(est, (int, float)) and est > 0:
        # Registry config values are provider-reference prices. API responses
        # rewrite est_price_usd to user-facing totals after this point.
        return float(est)

    fp = model.get("fallback_price") or {}
    if "per_run" in fp:
        return float(fp["per_run"])
    return None


def _config_provider_per_min(
    cfg: dict[str, Any],
    price: Optional[dict[str, Any]],
    model: dict[str, Any],
) -> tuple[Optional[float], Optional[str]]:
    if price:
        unit = str(price.get("unit") or "").lower()
        unit_price = float(price.get("unit_price") or 0.0)
        if unit_price > 0 and unit in ("minute", "minutes"):
            return unit_price, price.get("source", "live")
        if unit_price > 0 and unit in ("second", "seconds"):
            return unit_price * 60.0, price.get("source", "live")

    per_min = cfg.get("est_provider_price_usd_per_min")
    if isinstance(per_min, (int, float)) and per_min > 0:
        return float(per_min), "registry"

    per_min = cfg.get("est_price_usd_per_min")
    if isinstance(per_min, (int, float)) and per_min > 0:
        return float(per_min), "registry"

    fp = model.get("fallback_price") or {}
    if "per_min" in fp:
        return float(fp["per_min"]), "registry"
    return None, None


def _config_provider_per_second(
    cfg: dict[str, Any],
    price: Optional[dict[str, Any]],
    model: dict[str, Any],
) -> tuple[Optional[float], Optional[str]]:
    if price:
        unit = str(price.get("unit") or "").lower()
        unit_price = float(price.get("unit_price") or 0.0)
        if unit_price > 0 and unit in ("second", "seconds"):
            return unit_price, price.get("source", "live")
        if unit_price > 0 and unit in ("minute", "minutes"):
            return unit_price / 60.0, price.get("source", "live")

    per_second = cfg.get("est_provider_price_usd_per_second")
    if isinstance(per_second, (int, float)) and per_second > 0:
        return float(per_second), "registry"

    fp = model.get("fallback_price") or {}
    if "per_second" in fp:
        return float(fp["per_second"]), "registry"
    if "per_min" in fp:
        return float(fp["per_min"]) / 60.0, "registry"
    return None, None


def _estimate_config_provider_cost(
    cfg: dict[str, Any],
    price: dict[str, Any],
    model: dict[str, Any],
) -> Optional[float]:
    unit_price = float(price.get("unit_price") or 0.0)
    if unit_price <= 0:
        return None

    unit = str(price.get("unit") or "").strip().lower()
    unit = unit.replace("-", "_").replace(" ", "_")

    if unit in ("run", "request", "generation", "image", "output"):
        if _model_has_variable_config_prices(model):
            return None
        return unit_price

    if unit in ("second", "seconds", "sec", "secs", "video_second", "video_seconds"):
        duration = _config_duration_seconds(cfg)
        return unit_price * duration if duration is not None else None

    if unit in ("minute", "minutes", "min", "mins"):
        duration = _config_duration_seconds(cfg)
        if duration is not None:
            return unit_price * (duration / 60.0)
        return None

    if unit in ("character", "characters", "char", "chars"):
        chars = cfg.get("chars") or cfg.get("characters")
        return unit_price * float(chars) if isinstance(chars, (int, float)) and chars > 0 else None

    if unit in ("1k_characters", "thousand_characters"):
        chars = cfg.get("chars") or cfg.get("characters")
        return unit_price * (float(chars) / 1000.0) if isinstance(chars, (int, float)) and chars > 0 else None

    if unit in ("megapixel", "megapixels", "mp"):
        megapixels = _config_megapixels(cfg)
        return unit_price * megapixels if megapixels is not None else None

    return None


def _model_has_variable_config_prices(model: dict[str, Any]) -> bool:
    prices = {
        round(float(cfg["est_price_usd"]), 6)
        for cfg in (model.get("configs") or [])
        if isinstance(cfg.get("est_price_usd"), (int, float)) and cfg.get("est_price_usd") > 0
    }
    return len(prices) > 1


def _config_duration_seconds(cfg: dict[str, Any]) -> Optional[float]:
    duration = cfg.get("duration") or cfg.get("duration_s") or cfg.get("seconds")
    if isinstance(duration, (int, float)) and duration > 0:
        return float(duration)
    if isinstance(duration, str):
        try:
            return float(duration.strip().lower().removesuffix("s"))
        except ValueError:
            return None
    return None


def _config_megapixels(cfg: dict[str, Any]) -> Optional[float]:
    width = cfg.get("width")
    height = cfg.get("height")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
        return (float(width) * float(height)) / 1_000_000.0

    label = str(cfg.get("label") or "")
    match = re.search(r"(\d{3,5})\s*[×x]\s*(\d{3,5})", label)
    if not match:
        return None
    return (float(match.group(1)) * float(match.group(2))) / 1_000_000.0


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
