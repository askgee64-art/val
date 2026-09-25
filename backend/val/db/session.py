"""Async database session management and bootstrap."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from val.config import get_settings
from val.db.models import (
    Base,
    Organization,
    User,
    Agent,
    utcnow,
)

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables and seed founder org/user + core VAL agent."""
    settings.ensure_directories()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await _seed(session)
        await session.commit()


async def _seed(session: AsyncSession) -> None:
    org = await session.get(Organization, settings.founder_org_id)
    if org is None:
        org = Organization(
            org_id=settings.founder_org_id,
            name="VAL Internal",
            slug="val-internal",
            status="active",
            plan_tier="internal",
            settings={
                "max_autonomy_level": 2,
                "require_approval_above": 3,
            },
        )
        session.add(org)

    user = await session.get(User, settings.founder_user_id)
    if user is None:
        user = User(
            user_id=settings.founder_user_id,
            org_id=settings.founder_org_id,
            email=settings.founder_email,
            display_name=settings.founder_display_name,
            role="founder",
            status="active",
            last_login_at=utcnow(),
        )
        session.add(user)

    # Core VAL agent (the executive agent itself)
    result = await session.execute(
        select(Agent).where(
            Agent.org_id == settings.founder_org_id,
            Agent.name == "VAL",
        )
    )
    val_agent = result.scalar_one_or_none()
    if val_agent is None:
        session.add(
            Agent(
                org_id=settings.founder_org_id,
                name="VAL",
                role="executive",
                version="0.1.0",
                status="active",
                config={
                    "system_prompt": "You are VAL, the autonomous AI executive core.",
                    "model_prefs": {"default": settings.default_model},
                    "tool_allow_list": [
                        "echo",
                        "web_fetch",
                        "file_read",
                        "file_list",
                        "file_write",
                        "code_sandbox",
                        "memory_store",
                        "memory_recall",
                        "calculator",
                        "datetime_now",
                        "system_info",
                    ],
                    "memory_scope": ["working", "short_term", "long_term", "company"],
                },
                permissions={
                    "max_level": 2,
                    "can_request_level_4": True,
                    "can_delegate": False,  # MVP: no multi-agent yet
                },
                created_by=settings.founder_user_id,
            )
        )


async def health_check() -> bool:
    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
        return True
    except Exception:
        return False
