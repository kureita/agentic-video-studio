from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core import user as user_module
from app.models.usage import ActionType


@pytest.mark.asyncio
async def test_get_or_create_user_grants_signup_credit_on_first_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage_logs = SimpleNamespace(insert_one=AsyncMock())
    users = SimpleNamespace(
        find_one=AsyncMock(return_value=None),
        insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="new-user-id")),
        database=SimpleNamespace(usage_logs=usage_logs),
    )
    monkeypatch.setattr(user_module, "get_users_collection", lambda: users)

    user = await user_module.get_or_create_user(
        auth0_sub="auth0|new-user",
        email="new@example.com",
        name="New User",
    )

    assert user["_id"] == "new-user-id"
    assert user["usd_balance"] == 1.0
    users.insert_one.assert_awaited_once()
    usage_logs.insert_one.assert_awaited_once()

    usage_doc = usage_logs.insert_one.await_args.args[0]
    assert usage_doc["user_id"] == "new-user-id"
    assert usage_doc["action_type"] == ActionType.SIGNUP_BONUS
    assert usage_doc["total_usd"] == 1.0
    assert usage_doc["metadata"] == {"usd_added": 1.0}


@pytest.mark.asyncio
async def test_get_or_create_user_does_not_regrant_signup_credit_for_existing_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_user = {
        "_id": "existing-user-id",
        "auth0_sub": "auth0|existing-user",
        "email": "existing@example.com",
        "name": "Existing User",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "usd_balance": 3.5,
        "referral_code": "EXISTI_ABC123",
        "referred_by": None,
    }
    usage_logs = SimpleNamespace(insert_one=AsyncMock())
    users = SimpleNamespace(
        find_one=AsyncMock(return_value=existing_user.copy()),
        insert_one=AsyncMock(),
        update_one=AsyncMock(),
        database=SimpleNamespace(usage_logs=usage_logs),
    )
    monkeypatch.setattr(user_module, "get_users_collection", lambda: users)

    user = await user_module.get_or_create_user(
        auth0_sub="auth0|existing-user",
        email="existing@example.com",
        name="Existing User",
    )

    assert user["_id"] == "existing-user-id"
    assert user["usd_balance"] == 3.5
    users.insert_one.assert_not_awaited()
    usage_logs.insert_one.assert_not_awaited()
