"""Manage funds and vouchers for users.

Usage:
    cd apps/api

    # Add $50 directly to a user by email (local env)
    uv run -m scripts.manage_funds --env local add-balance --email test@example.com --amount 50

    # Create a $100 voucher (prod env, auto-generated code)
    uv run -m scripts.manage_funds --env prod create-voucher --amount 100

    # Create 5 × $10 vouchers at once
    uv run -m scripts.manage_funds --env prod create-voucher --amount 10 --count 5

    # Create a voucher with a custom code
    uv run -m scripts.manage_funds --env local create-voucher --amount 100 --code KUREITA_PROMO_100

    # List all unredeemed vouchers
    uv run -m scripts.manage_funds --env prod list-vouchers
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


async def add_balance(db, email: str, amount: float):
    if amount <= 0:
        print("❌ Amount must be greater than 0")
        return

    # Find user by email
    user = await db.users.find_one({"email": email})
    if not user:
        print(f"❌ User with email '{email}' not found.")
        return

    current_balance = user.get("usd_balance", 0.0)
    new_balance = round(current_balance + amount, 6)
    
    # Update balance
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "usd_balance": new_balance,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # Create a transaction record (optional but good for history)
    transaction = {
        "user_id": str(user["_id"]),
        "action_type": "deposit",
        "total_usd": amount,  # Positive amount for deposit
        "metadata": {
            "source": "admin_script",
            "note": f"Admin added ${amount:.2f}"
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.usage_logs.insert_one(transaction)

    print(f"✅ Successfully added ${amount:.2f} to {email}.")
    print(f"💰 Old balance: ${current_balance:.4f}")
    print(f"💰 New balance: ${new_balance:.4f}")


async def create_voucher(db, amount: float, custom_code: str = None, count: int = 1):
    if amount <= 0:
        print("❌ Amount must be greater than 0")
        return

    if custom_code and count > 1:
        print("❌ Cannot use --code with --count > 1 (codes must be unique). Omit --code for bulk creation.")
        return

    created = []
    for i in range(count):
        if custom_code:
            code = custom_code.strip().upper()
            # Check if code already exists
            existing = await db.vouchers.find_one({"code": code})
            if existing:
                print(f"❌ Voucher code '{code}' already exists.")
                return
        else:
            # Generate a clean random code — use int for whole-dollar amounts
            amount_str = str(int(amount)) if amount == int(amount) else f"{amount:.2f}".replace(".", "")
            random_suffix = str(uuid.uuid4().hex)[:8].upper()
            code = f"KUREITA_{amount_str}_{random_suffix}"

        now = datetime.now(timezone.utc)
        voucher = {
            "code": code,
            "usd_value": float(amount),
            "created_at": now,
            "is_redeemed": False,
            "redeemed_by": None,
            "redeemed_at": None,
            "created_by": "admin_script"
        }

        await db.vouchers.insert_one(voucher)
        created.append(code)
        print(f"✅ [{i+1}/{count}] Created voucher  🎟️  {code}  💵 ${amount:.2f}")

    if len(created) > 1:
        print(f"\n🎉 All {len(created)} vouchers created successfully!")


async def list_vouchers(db, show_redeemed: bool = False):
    """List vouchers from the database."""
    query = {} if show_redeemed else {"is_redeemed": False}
    cursor = db.vouchers.find(query).sort("created_at", -1)
    vouchers = await cursor.to_list(length=200)

    if not vouchers:
        status = "(including redeemed)" if show_redeemed else "unredeemed"
        print(f"ℹ️  No {status} vouchers found.")
        return

    status_label = "All" if show_redeemed else "Unredeemed"
    print(f"\n{'Code':<35} {'Value':>8}  {'Status':<12}  {'Redeemed By / Created At'}")
    print("-" * 85)
    for v in vouchers:
        code = v.get("code", "N/A")
        value = v.get("usd_value", 0.0)
        is_redeemed = v.get("is_redeemed", False)
        status = "✅ Redeemed" if is_redeemed else "🟢 Active"
        extra = v.get("redeemed_by", "") or str(v.get("created_at", ""))[:19]
        print(f"{code:<35} ${value:>7.2f}  {status:<12}  {extra}")
    print(f"\nTotal: {len(vouchers)} voucher(s) shown.")


async def main():
    parser = argparse.ArgumentParser(description="Manage Kureita funds and vouchers")
    
    # Global environment argument
    parser.add_argument("--env", type=str, choices=["local", "prod"], default="local", help="Environment to load (.env.local or .env.prod)")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add balance parser
    add_parser = subparsers.add_parser("add-balance", help="Add USD balance to a user")
    add_parser.add_argument("--email", required=True, help="User's email address")
    add_parser.add_argument("--amount", type=float, required=True, help="Amount in USD to add")

    # Create voucher parser
    voucher_parser = subparsers.add_parser("create-voucher", help="Create one or more redeemable vouchers")
    voucher_parser.add_argument("--amount", type=float, required=True, help="Value of the voucher in USD")
    voucher_parser.add_argument("--code", type=str, help="Optional custom code (single voucher only)")
    voucher_parser.add_argument("--count", type=int, default=1, help="Number of vouchers to create (default: 1)")

    # List vouchers parser
    list_parser = subparsers.add_parser("list-vouchers", help="List vouchers in the database")
    list_parser.add_argument("--all", dest="show_redeemed", action="store_true", help="Include already-redeemed vouchers")

    args = parser.parse_args()

    # Load appropriate .env file
    env_file = f".env.{args.env}"
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"📦 Loaded environment from {env_file}")
    else:
        print(f"⚠️  Warning: Environment file {env_file} not found.")

    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DATABASE", "kureita")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print(f"🔧 Connected to {mongo_url}/{db_name}\n")
    
    try:
        if args.command == "add-balance":
            await add_balance(db, args.email, args.amount)
        elif args.command == "create-voucher":
            await create_voucher(db, args.amount, args.code, args.count)
        elif args.command == "list-vouchers":
            await list_vouchers(db, args.show_redeemed)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
