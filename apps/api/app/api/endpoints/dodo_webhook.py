"""Dodo Payments webhook (Standard Webhooks signature verification)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from standardwebhooks import Webhook
from standardwebhooks.webhooks import WebhookVerificationError

from app.core.config import settings
from app.core.database import get_database
from app.services.billing import BillingService
from dodopayments.types.payment_succeeded_webhook_event import PaymentSucceededWebhookEvent

router = APIRouter()

META_USER = "kureita_auth0_sub"
META_CREDITS_USD = "kureita_credits_usd"


@router.post("/dodo/webhook")
async def dodo_payments_webhook(request: Request) -> Response:
    if not settings.dodo_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    db: AsyncIOMotorDatabase | None = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    raw = await request.body()
    headers = {
        "webhook-id": request.headers.get("webhook-id", ""),
        "webhook-signature": request.headers.get("webhook-signature", ""),
        "webhook-timestamp": request.headers.get("webhook-timestamp", ""),
    }

    try:
        payload = Webhook(settings.dodo_webhook_secret).verify(raw.decode("utf-8"), headers)
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if not isinstance(payload, dict) or payload.get("type") != "payment.succeeded":
        return Response(status_code=200)

    try:
        event = PaymentSucceededWebhookEvent.model_validate(payload)
    except Exception:
        return Response(status_code=200)

    payment = event.data
    payment_id = payment.payment_id
    meta = payment.metadata or {}
    user_sub = meta.get(META_USER)

    if not user_sub:
        return Response(status_code=200)

    # USD wallet credit: prefer checkout metadata (set only by our API). Customers may pay in INR etc.
    credits_raw = (meta.get(META_CREDITS_USD) or "").strip()
    amount: float | None = None
    if credits_raw:
        try:
            parsed = float(credits_raw)
        except ValueError:
            parsed = 0.0
        lo, hi = settings.dodo_min_topup_usd, settings.dodo_max_topup_usd
        if parsed > 0 and lo <= parsed <= hi:
            amount = round(parsed, 6)

    if amount is None:
        if payment.currency != "USD":
            return Response(status_code=200)
        amount = round(payment.total_amount / 100.0, 6)

    if amount <= 0:
        return Response(status_code=200)

    try:
        await db.dodo_payment_ledger.insert_one(
            {
                "payment_id": payment_id,
                "created_at": payment.created_at,
            }
        )
    except DuplicateKeyError:
        return Response(status_code=200)

    billing = BillingService(db)
    try:
        await billing.apply_deposit(
            user_sub,
            amount,
            metadata={
                "provider": "dodo_payments",
                "payment_id": payment_id,
                "checkout_session_id": payment.checkout_session_id,
                "dodo_environment": settings.dodo_payments_environment,
                "charge_total_minor": payment.total_amount,
                "charge_currency": payment.currency,
                "settlement_amount_minor": payment.settlement_amount,
                "settlement_currency": payment.settlement_currency,
                "credited_usd": amount,
            },
        )
    except Exception:
        await db.dodo_payment_ledger.delete_one({"payment_id": payment_id})
        raise HTTPException(status_code=500, detail="Failed to apply deposit; will retry")

    return Response(status_code=200)
