from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict

from app.core.database import get_database
from app.core.auth import get_current_user
from app.core.model_registry import get_models_for_api
from app.models.usage import UsageLog
from app.services.billing import BillingService


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


@router.get("/models")
async def get_models() -> Any:
    """
    Returns the full model registry for the frontend.
    Includes all featured image, video, audio, and LLM models with
    configs, pricing, AIR IDs, and capabilities.
    """
    return {"models": get_models_for_api()}


class ProcessReferralRequest(BaseModel):
    referral_code: str

class ProcessReferralResponse(BaseModel):
    success: bool
    message: str
    usd_awarded: float = 0.0

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
