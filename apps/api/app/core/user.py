"""User provisioning service.

Auto-creates user records in MongoDB on first authenticated API call.
Designed to be extended with credits, billing, and preferences later.
"""

from datetime import datetime, timezone

from app.core.database import get_users_collection


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
    user_doc = {
        "auth0_sub": auth0_sub,
        "email": email,
        "name": name,
        "created_at": now,
        "updated_at": now,
    }
    
    result = await collection.insert_one(user_doc)
    user_doc["_id"] = str(result.inserted_id)
    
    print(f"[User] Created new user: {auth0_sub} ({email})")
    
    return user_doc
