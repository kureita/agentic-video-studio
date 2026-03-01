from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.usage import ActionType, UsageLog
from app.models.user import User
from app.models.voucher import Voucher


class BillingService:
    # Pricing Matrix: Action -> Cost in Credits
    PRICING = {
        ActionType.AI_CHAT: 1,  # 1 credit per 10k tokens (handled via logic)
        ActionType.VIDEO_GEN: 10, # 10 credits per generation
        ActionType.IMAGE_GEN: 1,  # 1 credit per generation
        ActionType.AUDIO_GEN: 2,  # 2 credits per generation
        ActionType.RENDER: 20,    # 20 credits for final export
    }

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

    async def get_user_balance(self, user_id: str) -> int:
        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        return user_doc.get("credits_balance", 0)

    async def deduct_credits(
        self,
        user_id: str,
        action: ActionType,
        custom_cost: Optional[int] = None,
        tokens_used: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> int:
        """
        Deducts credits from a user's balance and logs the usage.
        Raises 402 Payment Required if insufficient funds.
        """
        cost = custom_cost if custom_cost is not None else self.PRICING.get(action, 0)

        # AI Chat special logic (1 credit per 10k tokens) - allows 0 cost for short <5k tokens
        if action == ActionType.AI_CHAT and tokens_used is not None:
            cost = round(tokens_used / 10000)

        # 1. Check balance
        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        user_oid = user_doc["_id"]

        current_balance = user_doc.get("credits_balance", 0)
        
        if cost > 0 and current_balance < cost:
            raise HTTPException(
                status_code=402, 
                detail=f"Insufficient credits. Required: {cost}, Available: {current_balance}"
            )

        # 2. Deduct credits
        new_balance = current_balance - cost
        if cost > 0:
            await self.db.users.update_one(
                {"_id": user_oid},
                {"$set": {"credits_balance": new_balance, "updated_at": datetime.utcnow()}}
            )

        # 3. Log usage regardless of cost
        usage_log = UsageLog(
            user_id=str(user_oid),
            action_type=action,
            tokens_used=tokens_used,
            credits_deducted=cost,
            metadata=metadata or {}
        )
        await self.db.usage_logs.insert_one(usage_log.model_dump(by_alias=True, exclude_none=True))

        return new_balance

    async def redeem_voucher(self, user_id: str, code: str) -> int:
        """
        Redeems a voucher code and adds credits to the user's balance.
        """
        user_doc = await self._resolve_user(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        user_oid = user_doc["_id"]
            
        # 1. Find and validate voucher
        voucher_doc = await self.db.vouchers.find_one({"code": code})
        if not voucher_doc:
            raise HTTPException(status_code=404, detail="Voucher not found")
            
        voucher = Voucher(**voucher_doc)
        
        if voucher.is_redeemed:
            raise HTTPException(status_code=400, detail="Voucher has already been redeemed")

        # 2. Mark voucher as redeemed
        result = await self.db.vouchers.update_one(
            {"code": code, "is_redeemed": False}, # Atomic check
            {"$set": {
                "is_redeemed": True,
                "redeemed_by": str(user_oid),
                "redeemed_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
             raise HTTPException(status_code=400, detail="Failed to redeem voucher. It may have just been used.")

        # 3. Add credits to user
        user_doc = await self.db.users.find_one({"_id": user_oid})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        new_balance = user_doc.get("credits_balance", 0) + voucher.credit_value
        await self.db.users.update_one(
            {"_id": user_oid},
            {"$set": {"credits_balance": new_balance, "updated_at": datetime.utcnow()}}
        )
        
        # 4. Log usage
        usage_log = UsageLog(
            user_id=str(user_oid),
            action_type=ActionType.VOUCHER_REDEEM,
            credits_deducted=-voucher.credit_value, # Negative deduction is addition
            metadata={"voucher_code": code}
        )
        await self.db.usage_logs.insert_one(usage_log.model_dump(by_alias=True, exclude_none=True))

        return new_balance
        
    async def process_referral(self, new_user_id: str, referral_code: str):
        """
        Processes a referral code, granting 500 credits to both parties.
        """
        from bson import ObjectId
        from datetime import timezone
        
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
            
        # 3. Award credits to both (500 each)
        await self.db.users.update_one(
            {"_id": referrer_id},
            {"$inc": {"credits_balance": 500}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        
        await self.db.users.update_one(
            {"_id": user_oid},
            {"$inc": {"credits_balance": 500}, "$set": {"referred_by": str(referrer_id), "updated_at": datetime.now(timezone.utc)}}
        )
        
        # 4. Log usage for both users
        referrer_log = UsageLog(
            user_id=str(referrer_id),
            action_type=ActionType.REFERRAL_BONUS,
            credits_deducted=-500,
            metadata={"referred_user_id": str(user_oid)}
        )
        new_user_log = UsageLog(
            user_id=str(user_oid),
            action_type=ActionType.REFERRAL_BONUS,
            credits_deducted=-500,
            metadata={"referred_by_id": str(referrer_id), "referral_code": referral_code}
        )
        await self.db.usage_logs.insert_many([
            referrer_log.model_dump(by_alias=True, exclude_none=True),
            new_user_log.model_dump(by_alias=True, exclude_none=True)
        ])
        
        return {"success": True, "message": "Referral processed successfully", "credits_awarded": 500}

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
