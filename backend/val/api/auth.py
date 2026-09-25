"""Authentication and authorization dependencies for VAL API.

MVP focuses on single-user founder authentication (Document 30 §3).
Supports Bearer token, X-VAL-Founder-Key header, and development fallback.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from val.config import get_settings
from val.db.models import User
from val.db.session import get_session

settings = get_settings()


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_val_key: Annotated[str | None, Header(alias="x-val-founder-key")] = None,
    session: AsyncSession = Depends(get_session),
) -> User:
    token: str | None = None
    if x_val_key:
        token = x_val_key.strip()
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    # Development auto-authentication if matching token or in debug mode
    if token == settings.founder_token or (settings.debug and token is None):
        user = await session.get(User, settings.founder_user_id)
        if user:
            return user

    if token != settings.founder_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_or_missing_founder_token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await session.get(User, settings.founder_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="founder_user_record_missing",
        )
    return user
