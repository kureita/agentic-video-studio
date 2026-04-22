from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.models.usage import ActionType, UsageLog
from app.models.user import User
from app.models.voucher import Voucher


class BillingService:
    """Cost-based billing service using actual API costs + commission."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def _resolve_user(self, user_id: str) -> Optional[dict]:
        from bson import ObjectId
        # First, query by auth0_sub
        user_doc = await self.db.users.find_one({"auth0_sub": user_id})
        if user_doc:
            return user_doc
            
        # Fallback to internal ObjectId lookup
        try:
            user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
            return await self.db.users.find_one({"_id": user_oid})
        except:
            return None

    async def get_user_balance(self, user_id: str) -> float:
        """Returns the user's current USD balance."""
        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        return user_doc.get("usd_balance", 0.0)

    async def charge_usage(
        self,
        user_id: str,
        action: ActionType,
        cost_usd: float,
        model_id: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        tokens_used: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> float:
        """
        Charges a user for API usage based on actual cost + commission.
        
        Args:
            user_id: Auth0 sub or internal ObjectId
            action: Type of action (IMAGE_GEN, VIDEO_GEN, etc.)
            cost_usd: Actual cost from provider API response
            model_id: Registry model ID (e.g. "gpt-image-1-5")
            model_name: Human-readable model name (e.g. "GPT Image 1.5")
            provider: Provider name (e.g. "OpenAI", "fal.ai")
            tokens_used: Token count for LLM actions
            metadata: Additional metadata to log
            
        Returns:
            New USD balance after deduction
            
        Raises:
            HTTPException 402 if insufficient balance
            HTTPException 404 if user not found
        """
        # Calculate commission
        commission_usd = round(cost_usd * settings.commission_multiplier, 6)
        total_usd = round(cost_usd + commission_usd, 6)

        # 1. Check balance
        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        user_oid = user_doc["_id"]
        current_balance = user_doc.get("usd_balance", 0.0)
        
        if total_usd > 0 and current_balance < total_usd:
            raise HTTPException(
                status_code=402, 
                detail=f"Insufficient balance. Required: ${total_usd:.4f}, Available: ${current_balance:.4f}"
            )

        # 2. Deduct balance
        new_balance = round(current_balance - total_usd, 6)
        if total_usd > 0:
            await self.db.users.update_one(
                {"_id": user_oid},
                {"$set": {"usd_balance": new_balance, "updated_at": datetime.now(timezone.utc)}}
            )

        # 3. Log usage
        usage_log = UsageLog(
            user_id=str(user_oid),
            action_type=action,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            commission_usd=commission_usd,
            total_usd=total_usd,
            model_id=model_id,
            model_name=model_name,
            provider=provider,
            metadata=metadata or {},
        )
        await self.db.usage_logs.insert_one(usage_log.model_dump(by_alias=True, exclude_none=True))

        return new_balance

    async def redeem_voucher(self, user_id: str, code: str) -> float:
        """
        Redeems a voucher code and adds USD amount to the user's balance.
        Returns new balance.
        """
        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        user_oid = user_doc["_id"]
            
        # 1. Find and validate voucher (case-insensitive code lookup)
        code_upper = code.strip().upper()
        voucher_doc = await self.db.vouchers.find_one({"code": code_upper})
        if not voucher_doc:
            raise HTTPException(status_code=404, detail="Voucher not found")
            
        # Use model_validate so the _id ObjectId is correctly parsed via the alias
        voucher = Voucher.model_validate(voucher_doc)
        
        if voucher.is_redeemed:
            raise HTTPException(status_code=400, detail="Voucher has already been redeemed")

        # 2. Mark voucher as redeemed
        result = await self.db.vouchers.update_one(
            {"code": code_upper, "is_redeemed": False},  # Atomic check — prevent double-spend
            {"$set": {
                "is_redeemed": True,
                "redeemed_by": str(user_oid),
                "redeemed_at": datetime.now(timezone.utc),
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Failed to redeem voucher. It may have just been used.")

        # 3. Add USD to user balance
        user_doc = await self.db.users.find_one({"_id": user_oid})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        new_balance = round(user_doc.get("usd_balance", 0.0) + voucher.usd_value, 6)
        await self.db.users.update_one(
            {"_id": user_oid},
            {"$set": {"usd_balance": new_balance, "updated_at": datetime.now(timezone.utc)}}
        )
        
        # 4. Log usage  (total_usd is positive here = funds deposited)
        usage_log = UsageLog(
            user_id=str(user_oid),
            action_type=ActionType.VOUCHER_REDEEM,
            cost_usd=0.0,
            commission_usd=0.0,
            total_usd=voucher.usd_value,  # Positive = USD added to balance
            metadata={"voucher_code": code_upper, "usd_added": voucher.usd_value},
        )
        await self.db.usage_logs.insert_one(usage_log.model_dump(by_alias=True, exclude_none=True))

        return new_balance

    async def apply_deposit(
        self,
        user_id: str,
        amount_usd: float,
        metadata: Optional[dict] = None,
    ) -> float:
        """
        Add USD to balance and log a deposit (e.g. Dodo Payments webhook).
        user_id: Auth0 subject or internal id (same resolution as other billing methods).
        """
        if amount_usd <= 0:
            raise HTTPException(status_code=400, detail="Deposit amount must be positive")

        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        user_oid = user_doc["_id"]
        new_balance = round(user_doc.get("usd_balance", 0.0) + amount_usd, 6)
        await self.db.users.update_one(
            {"_id": user_oid},
            {"$set": {"usd_balance": new_balance, "updated_at": datetime.now(timezone.utc)}},
        )

        usage_log = UsageLog(
            user_id=str(user_oid),
            action_type=ActionType.DEPOSIT,
            cost_usd=0.0,
            commission_usd=0.0,
            total_usd=amount_usd,
            metadata=metadata or {},
        )
        await self.db.usage_logs.insert_one(usage_log.model_dump(by_alias=True, exclude_none=True))
        return new_balance

    async def process_referral(self, new_user_id: str, referral_code: str):
        """
        Processes a referral code, granting $5.00 USD to both parties.
        """
        from bson import ObjectId
        
        REFERRAL_BONUS_USD = 5.00
        
        # 1. Find referrer
        referrer_doc = await self.db.users.find_one({"referral_code": referral_code})
        if not referrer_doc:
            return {"success": False, "message": "Invalid referral code"}
            
        referrer_id = referrer_doc["_id"]
        
        # 2. Check if new user already has a referrer (prevent double dipping)
        new_user = await self._resolve_user(new_user_id)
        if not new_user:
            return {"success": False, "message": "Invalid user ID"}
            
        user_oid = new_user["_id"]
        
        if new_user.get("referred_by"):
            return {"success": False, "message": "User already referred"}
            
        # 3. Award USD to both
        await self.db.users.update_one(
            {"_id": referrer_id},
            {"$inc": {"usd_balance": REFERRAL_BONUS_USD}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        
        await self.db.users.update_one(
            {"_id": user_oid},
            {"$inc": {"usd_balance": REFERRAL_BONUS_USD}, "$set": {"referred_by": str(referrer_id), "updated_at": datetime.now(timezone.utc)}}
        )
        
        # 4. Log usage for both users
        referrer_log = UsageLog(
            user_id=str(referrer_id),
            action_type=ActionType.REFERRAL_BONUS,
            cost_usd=0.0,
            commission_usd=0.0,
            total_usd=-REFERRAL_BONUS_USD,  # Negative = addition
            metadata={"referred_user_id": str(user_oid)},
        )
        new_user_log = UsageLog(
            user_id=str(user_oid),
            action_type=ActionType.REFERRAL_BONUS,
            cost_usd=0.0,
            commission_usd=0.0,
            total_usd=-REFERRAL_BONUS_USD,  # Negative = addition
            metadata={"referred_by_id": str(referrer_id), "referral_code": referral_code},
        )
        await self.db.usage_logs.insert_many([
            referrer_log.model_dump(by_alias=True, exclude_none=True),
            new_user_log.model_dump(by_alias=True, exclude_none=True)
        ])
        
        return {"success": True, "message": "Referral processed successfully", "usd_awarded": REFERRAL_BONUS_USD}

    async def get_usage_history(
        self, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0, 
        action_type: Optional[ActionType] = None
    ) -> dict:
        """
        Retrieves usage history for a user, with optional filtering and pagination.
        """
        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            return {
                "logs": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
            
        user_oid_str = str(user_doc["_id"])
        
        query = {"user_id": user_oid_str}
        if action_type:
            query["action_type"] = action_type
            
        cursor = self.db.usage_logs.find(query).sort("created_at", -1).skip(offset).limit(limit)
        logs = await cursor.to_list(length=limit)
        total = await self.db.usage_logs.count_documents(query)
        
        # Parse MongoDB docs to UsageLog objects
        parsed_logs = [UsageLog(**log) for log in logs]
        
        return {
            "logs": parsed_logs,
            "total": total,
            "limit": limit,
            "offset": offset
        }
