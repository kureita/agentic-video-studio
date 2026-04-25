"""Auth0 JWT validation for FastAPI.

Validates Bearer tokens against Auth0's JWKS endpoint and provides
a `get_current_user` dependency that returns the authenticated user dict.
"""

import httpx
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

security = HTTPBearer()


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch and cache Auth0 JWKS (JSON Web Key Set)."""
    jwks_url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
    response = httpx.get(jwks_url, timeout=10)
    response.raise_for_status()
    return response.json()


def _get_signing_key(token: str) -> dict:
    """Extract the correct signing key from JWKS for the given token."""
    try:
        jwks = _get_jwks()
    except Exception as e:
        # JWKS unavailable shouldn't surface as 500 — the request is
        # unauthenticated until we can verify the signing key.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to fetch signing keys: {e!s}",
        ) from e

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed token: {e!s}",
        ) from e

    for key in jwks.get("keys", []):
        if key["kid"] == unverified_header.get("kid"):
            return key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find appropriate signing key",
    )


def decode_token(token: str) -> dict:
    """Decode and validate an Auth0 JWT token."""
    signing_key = _get_signing_key(token)

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[settings.auth0_algorithms],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )


async def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency: validate Bearer token and return decoded payload.

    The payload contains:
    - sub: Auth0 user ID (e.g. "auth0|abc123")
    - email: user email (if available in token)
    - permissions: list of permissions (if configured)
    """
    return decode_token(credentials.credentials)


async def get_current_user(
    token_payload: dict = Depends(get_current_user_token),
) -> dict:
    """FastAPI dependency: get or create user from token, return user dict.

    This auto-provisions users in MongoDB on first API call.
    """
    from app.core.user import get_or_create_user

    user = await get_or_create_user(
        auth0_sub=token_payload.get("sub", ""),
        email=token_payload.get("email") or token_payload.get(f"https://{settings.auth0_domain}/email", ""),
        name=token_payload.get("name") or token_payload.get(f"https://{settings.auth0_domain}/name", ""),
    )
    return user
