"""Pytest configuration and test fixtures for VAL."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment
os.environ["VAL_ENV"] = "testing"
os.environ["VAL_DEBUG"] = "true"

TEST_DATA_DIR = Path("/home/user/val/data_test")
os.environ["VAL_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DATA_DIR / 'test_val.db'}"

from val.config import get_settings
from val.db.models import Base
from val.db.session import _seed

settings = get_settings()


@pytest.fixture(scope="session", autouse=True)
def setup_test_directories():
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)


@pytest_asyncio.fixture
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DATA_DIR / 'test_val.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await _seed(session)
        await session.commit()
        yield session

    await engine.dispose()
