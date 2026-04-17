"""User provisioning service.

Auto-creates user records in MongoDB on first authenticated API call.
Designed to be extended with credits, billing, and preferences later.
"""

import uuid
from datetime import datetime, timezone

from app.core.database import get_users_collection
from app.models.usage import ActionType, UsageLog


SIGNUP_BONUS_USD = 1.0


async def get_or_create_user(auth0_sub: str, email: str = "", name: str = "") -> dict:
    """Look up user by Auth0 sub; create if not found.

    Returns a dict with: _id (str), auth0_sub, email, name, created_at
    """
    collection = get_users_collection()
    
    # Try to find existing user
    user = await collection.find_one({"auth0_sub": auth0_sub})
    
    if user:
        # Update email/name if they've changed
        updates = {}
        if email and email != user.get("email"):
            updates["email"] = email
        if name and name != user.get("name"):
            updates["name"] = name
        if updates:
            updates["updated_at"] = datetime.now(timezone.utc)
            await collection.update_one(
                {"_id": user["_id"]},
                {"$set": updates},
            )
            user.update(updates)
        
        user["_id"] = str(user["_id"])
        return user
    
    # Create new user
    now = datetime.now(timezone.utc)
    
    # Generate a unique referral code
    base_code = email.split('@')[0].upper()[:6] if email else "USER"
    random_suffix = str(uuid.uuid4().hex)[:6].upper()
    referral_code = f"{base_code}_{random_suffix}"
    
    user_doc = {
        "auth0_sub": auth0_sub,
        "email": email,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "usd_balance": SIGNUP_BONUS_USD,
        "referral_code": referral_code,
        "referred_by": None
    }
    
    result = await collection.insert_one(user_doc)
    user_doc["_id"] = str(result.inserted_id)

    usage_log = UsageLog(
        user_id=user_doc["_id"],
        action_type=ActionType.SIGNUP_BONUS,
        cost_usd=0.0,
        commission_usd=0.0,
        total_usd=SIGNUP_BONUS_USD,
        metadata={"usd_added": SIGNUP_BONUS_USD},
    )
    await collection.database.usage_logs.insert_one(
        usage_log.model_dump(by_alias=True, exclude_none=True)
    )
    
    print(
        f"[User] Created new user: {auth0_sub} ({email}) with "
        f"${SIGNUP_BONUS_USD:.2f} balance. Referral code: {referral_code}"
    )
    
    return user_doc
