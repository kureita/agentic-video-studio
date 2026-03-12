"""Cleanup old credit-based billing data from MongoDB.

This script:
1. Renames `credits_balance` → `usd_balance` on all users (sets to 0.0)
2. Renames `credit_value` → `usd_value` on all vouchers
3. Drops old `usage_logs` collection (incompatible schema)

Usage:
    cd apps/api
    python -m scripts.cleanup_old_billing

Set MONGODB_URL and MONGODB_DATABASE env vars, or it defaults to local dev.
"""

import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DATABASE", "kureita")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print(f"🔧 Connected to {mongo_url}/{db_name}")
    
    # 1. Migrate users: credits_balance → usd_balance
    users_count = await db.users.count_documents({"credits_balance": {"$exists": True}})
    if users_count > 0:
        result = await db.users.update_many(
            {"credits_balance": {"$exists": True}},
            {
                "$set": {"usd_balance": 0.0},
                "$unset": {"credits_balance": ""},
            }
        )
        print(f"✅ Migrated {result.modified_count} users: credits_balance → usd_balance (reset to $0.00)")
    else:
        print("ℹ️  No users with credits_balance found — already migrated or empty")
    
    # 2. Migrate vouchers: credit_value → usd_value
    vouchers_count = await db.vouchers.count_documents({"credit_value": {"$exists": True}})
    if vouchers_count > 0:
        # Convert credit_value (int) to usd_value (float) — rough conversion
        # 1000 credits ≈ $10.00 (adjust ratio as needed)
        cursor = db.vouchers.find({"credit_value": {"$exists": True}})
        async for voucher in cursor:
            credit_val = voucher.get("credit_value", 0)
            usd_val = round(credit_val / 100, 2)  # 100 credits = $1.00
            await db.vouchers.update_one(
                {"_id": voucher["_id"]},
                {
                    "$set": {"usd_value": usd_val},
                    "$unset": {"credit_value": ""},
                }
            )
        print(f"✅ Migrated {vouchers_count} vouchers: credit_value → usd_value")
    else:
        print("ℹ️  No vouchers with credit_value found — already migrated or empty")
        
    # 2.5 Migrate vouchers: redeemed → is_redeemed (schema fix)
    vouchers_fix_count = await db.vouchers.count_documents({"redeemed": {"$exists": True}})
    if vouchers_fix_count > 0:
        result = await db.vouchers.update_many(
            {"redeemed": {"$exists": True}},
            [
                {"$set": {"is_redeemed": "$redeemed"}},
                {"$unset": ["redeemed"]}
            ]
        )
        print(f"✅ Migrated {result.modified_count} vouchers: redeemed → is_redeemed")
    
    # 3. Drop old usage_logs (incompatible schema — had credits_deducted)
    existing_logs = await db.usage_logs.count_documents({})
    if existing_logs > 0:
        confirm = input(f"⚠️  Drop {existing_logs} old usage_logs? (y/N): ").strip().lower()
        if confirm == "y":
            await db.usage_logs.drop()
            print(f"✅ Dropped usage_logs collection ({existing_logs} documents)")
        else:
            print("⏭️  Skipped dropping usage_logs")
    else:
        print("ℹ️  usage_logs collection is empty — nothing to drop")
    
    print("\n🎉 Cleanup complete!")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
