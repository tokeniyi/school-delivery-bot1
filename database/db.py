from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL

# Create async PostgreSQL engine.
# pool_pre_ping=True validates connections before use to recover from stale connections.
# echo=False in production; set echo=True only for debug sessions.
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# Configure the async session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency generator to get DB session instances
async def get_db():
    async with async_session() as session:
        yield session
