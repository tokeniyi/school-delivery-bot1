from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Async SQLite connection URL
# school_delivery.db will be created in the directory from which the application is run (project root)
DATABASE_URL = "sqlite+aiosqlite:///school_delivery.db"

# Create async engine. echo=True prints SQL queries to console (useful for dev/debugging)
engine = create_async_engine(DATABASE_URL, echo=True)

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
