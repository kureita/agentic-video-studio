from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.core.database import get_database
from app.core.auth import get_current_user
from app.core.model_registry import get_models_for_api
from app.models.usage import UsageLog
from app.services.billing import BillingService
from app.services.dodo_service import create_topup_checkout_session
from app.services.fal_pricing import FalPricingService


router = APIRouter(prefix="/billing", tags=["billing"])

def get_billing_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> BillingService:
    return BillingService(db)

class BalanceResponse(BaseModel):
    balance: float  # USD balance
    user_id: str

class RedeemRequest(BaseModel):
    code: str

class UsageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    logs: List[UsageLog]
    total: int


class DodoTopupConfigResponse(BaseModel):
    payments_enabled: bool
    environment: str
    min_usd: float
    max_usd: float


class DodoCheckoutRequest(BaseModel):
    amount_usd: float = Field(..., gt=0, description="USD to add (within configured min/max)")
    # Auth0 API access tokens often omit `email`; the SPA can send the profile email from the ID token.
    customer_email: Optional[str] = Field(default=None, max_length=320)

    @field_validator("customer_email")
    @classmethod
    def strip_optional_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class DodoCheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str
    environment: str


class ProcessReferralRequest(BaseModel):
    referral_code: str


class ProcessReferralResponse(BaseModel):
    success: bool
    message: str
    usd_awarded: float = 0.0


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: dict = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> Any:
    """
    Get the current USD balance for the user.
    """
    user_id = current_user["auth0_sub"]
    balance = await billing_service.get_user_balance(user_id)
    return {"balance": balance, "user_id": user_id}


@router.post("/redeem", response_model=BalanceResponse)
async def redeem_voucher(
    request: RedeemRequest,
    current_user: dict = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> Any:
    """
    Redeem a voucher code and add USD to the user's balance.
    """
    user_id = current_user["auth0_sub"]
    new_balance = await billing_service.redeem_voucher(user_id, request.code)
    return {"balance": new_balance, "user_id": user_id}


@router.get("/usage", response_model=UsageResponse)
async def get_usage_logs(
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> Any:
    """
    Get the usage logs for the user.
    """
    user_id = current_user["auth0_sub"]
    result = await billing_service.get_usage_history(user_id=user_id, limit=limit, offset=skip)
    return {"logs": result["logs"], "total": result["total"]}


@router.get("/dodo/topup-config", response_model=DodoTopupConfigResponse)
async def dodo_topup_config(
    current_user: dict = Depends(get_current_user),
) -> Any:
    """Min/max USD and whether card top-up is configured (single pay-what-you-want product)."""
    enabled = bool(settings.dodo_payments_api_key and settings.dodo_topup_product_id.strip())
    return DodoTopupConfigResponse(
        payments_enabled=enabled,
        environment=settings.dodo_payments_environment,
        min_usd=settings.dodo_min_topup_usd,
        max_usd=settings.dodo_max_topup_usd,
    )


@router.post("/dodo/checkout-session", response_model=DodoCheckoutResponse)
async def dodo_create_checkout_session(
    request: DodoCheckoutRequest,
    current_user: dict = Depends(get_current_user),
) -> Any:
    """Start Dodo hosted checkout; credits are applied via webhook after payment succeeds."""
    if not settings.dodo_payments_api_key:
        raise HTTPException(status_code=503, detail="Card payments are not configured")

    product_id = settings.dodo_topup_product_id.strip()
    if not product_id:
        raise HTTPException(status_code=503, detail="Top-up product is not configured (DODO_TOPUP_PRODUCT_ID)")

    lo, hi = settings.dodo_min_topup_usd, settings.dodo_max_topup_usd
    if request.amount_usd < lo or request.amount_usd > hi:
        raise HTTPException(
            status_code=400,
            detail=f"Amount must be between ${lo:.2f} and ${hi:.2f} USD",
        )

    amount_cents = int(round(request.amount_usd * 100))
    min_cents = int(round(lo * 100))
    max_cents = int(round(hi * 100))
    if amount_cents < min_cents or amount_cents > max_cents:
        raise HTTPException(status_code=400, detail="Amount out of allowed range after rounding")

    email = (request.customer_email or current_user.get("email") or "").strip()
    if email and "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address for checkout")

    name = (current_user.get("name") or "").strip() or email
    if not email:
        raise HTTPException(
            status_code=400,
            detail=(
                "No email on file for checkout. Ensure your Auth0 user has an email, "
                "or sign in with a social provider that shares email."
            ),
        )

    if request.customer_email and not (current_user.get("email") or "").strip():
        db = get_database()
        if db is not None:
            await db.users.update_one(
                {"auth0_sub": current_user["auth0_sub"]},
                {"$set": {"email": email, "updated_at": datetime.now(timezone.utc)}},
            )

    user_sub = current_user["auth0_sub"]
    return_url = f"{settings.web_app_url.rstrip('/')}/usage?payment=success"

    # Carried into the signed webhook so we credit USD wallet balance even when Dodo charges in INR/etc.
    credits_usd = round(request.amount_usd, 6)
    metadata = {
        "kureita_auth0_sub": user_sub,
        "kureita_credits_usd": str(credits_usd),
    }

    try:
        session_id, checkout_url = create_topup_checkout_session(
            product_id=product_id,
            amount_cents=amount_cents,
            customer_email=email,
            customer_name=name,
            return_url=return_url,
            metadata=metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dodo checkout failed: {e!s}") from e

    return DodoCheckoutResponse(
        session_id=session_id,
        checkout_url=checkout_url,
        environment=settings.dodo_payments_environment,
    )


@router.get("/models")
async def get_models(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Any:
    """
    Returns the full model registry for the frontend.
    Includes all featured image, video, audio, and LLM models with
    configs, live fal-based user-facing price estimates, AIR IDs, and capabilities.
    """
    pricing = FalPricingService(db)
    return {"models": await pricing.enrich_models_for_user_estimates(get_models_for_api())}


@router.post("/process-referral", response_model=ProcessReferralResponse)
async def process_referral(
    request: ProcessReferralRequest,
    current_user: dict = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> Any:
    """
    Process a referral code for a new user.
    """
    user_id = current_user["auth0_sub"]
    result = await billing_service.process_referral(
        new_user_id=user_id,
        referral_code=request.referral_code
    )
    
    return ProcessReferralResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
        usd_awarded=result.get("usd_awarded", 0.0)
    )
