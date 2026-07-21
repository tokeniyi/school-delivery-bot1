import os
import sys
import asyncio
import pytest
import services.notifications as notifications

# Force SelectorEventLoop on Windows to avoid ProactorEventLoop issues
# with asyncpg + SQLAlchemy greenlets
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("ADMIN_IDS", "123456789")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@postgres:5432/schoolbridge")
os.environ.setdefault("REDIS_URL", "redis://schoolbridge-redis:6379/0")


class FakeBot:
    def __init__(self, raise_on=None):
        self.sent = []
        self.raise_on = set(raise_on or [])

    async def send_message(self, chat_id, text, **kwargs):
        if chat_id in self.raise_on:
            raise RuntimeError(f"Simulated send failure for {chat_id}")
        self.sent.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})


@pytest.fixture(autouse=True)
async def clean_db():
    """Remove all rows before each test for isolation."""
    import asyncpg
    
    # Read DATABASE_URL from environment to avoid stale config module state
    dsn = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:password@postgres:5432/schoolbridge")
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        users_before = await conn.fetchval("SELECT COUNT(*) FROM users")
        reqs_before = await conn.fetchval("SELECT COUNT(*) FROM student_requests")
        travels_before = await conn.fetchval("SELECT COUNT(*) FROM parent_travels")
        matches_before = await conn.fetchval("SELECT COUNT(*) FROM matches")
        print(f"\n[clean_db] BEFORE: users={users_before}, reqs={reqs_before}, travels={travels_before}, matches={matches_before}")
        
        await conn.execute("DELETE FROM matches")
        await conn.execute("DELETE FROM student_requests")
        await conn.execute("DELETE FROM parent_travels")
        await conn.execute("DELETE FROM users")
        
        users_after = await conn.fetchval("SELECT COUNT(*) FROM users")
        reqs_after = await conn.fetchval("SELECT COUNT(*) FROM student_requests")
        travels_after = await conn.fetchval("SELECT COUNT(*) FROM parent_travels")
        matches_after = await conn.fetchval("SELECT COUNT(*) FROM matches")
        print(f"[clean_db] AFTER: users={users_after}, reqs={reqs_after}, travels={travels_after}, matches={matches_after}")
    finally:
        await conn.close()
    
    # Dispose pooled connections so the next test gets fresh connections
    # that see the committed deletes above.
    from database.db import engine
    await engine.dispose()
    
    yield


@pytest.fixture
def fake_bot():
    bot = FakeBot()
    notifications._notification_bot = bot
    return bot