import pytest
import asyncio
from sqlalchemy import delete
from database.db import async_session
from database.crud import create_tables
from database.models import User, StudentRequest, ParentTravel, Match
import services.notifications as notifications


class FakeBot:
    def __init__(self, raise_on=None):
        self.sent = []
        self.raise_on = set(raise_on or [])

    async def send_message(self, chat_id, text, **kwargs):
        if chat_id in self.raise_on:
            raise RuntimeError(f"Simulated send failure for {chat_id}")
        self.sent.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})


@pytest.fixture(autouse=True)
def clean_db():
    """Create tables and remove all rows before each test for isolation (runs sync by calling asyncio.run)."""
    async def _c():
        await create_tables()
        async with async_session() as session:
            await session.execute(delete(Match))
            await session.execute(delete(StudentRequest))
            await session.execute(delete(ParentTravel))
            await session.execute(delete(User))
            await session.commit()
    asyncio.run(_c())
    yield


@pytest.fixture
def fake_bot():
    bot = FakeBot()
    notifications._notification_bot = bot
    return bot


@pytest.fixture
def anyio_backend():
    # allow pytest-asyncio / anyio compatibility if used
    return 'asyncio'