"""Dodo Payments checkout session creation (test vs live from settings.app_env)."""

from __future__ import annotations

from dodopayments import DodoPayments

from app.core.config import settings


def get_dodo_client() -> DodoPayments:
    return DodoPayments(
        bearer_token=settings.dodo_payments_api_key,
        environment=settings.dodo_payments_environment,
    )


def create_topup_checkout_session(
    *,
    product_id: str,
    amount_cents: int,
    customer_email: str,
    customer_name: str,
    return_url: str,
    metadata: dict[str, str],
) -> tuple[str, str]:
    """
    Returns (session_id, checkout_url).

    ``product_id`` must be a one-time Dodo product with pay-what-you-want enabled.
    ``amount_cents`` is the USD charge in cents (SDK: ProductItemReqParam.amount).
    """
    client = get_dodo_client()
    session = client.checkout_sessions.create(
        product_cart=[{"product_id": product_id, "quantity": 1, "amount": amount_cents}],
        customer={"email": customer_email, "name": customer_name or customer_email},
        return_url=return_url,
        metadata=metadata,
    )
    return session.session_id, session.checkout_url
