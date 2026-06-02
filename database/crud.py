from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.db import engine
from database.models import Base, User, StudentRequest

async def create_tables():
    """Create all database tables asynchronously on startup if they don't exist."""
    async with engine.begin() as conn:
        # Create all tables registered with Base
        await conn.run_sync(Base.metadata.create_all)

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Retrieve user record by Telegram ID."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def create_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None) -> User:
    """Insert new user if not exists; prevent duplicates. Updates username and name if changed."""
    existing_user = await get_user_by_telegram_id(session, telegram_id)
    if existing_user:
        existing_user.username = username
        existing_user.full_name = full_name
        await session.commit()
        return existing_user

    new_user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        role="Student"  # Default role mapped by DB schema
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user

async def update_user_role(session: AsyncSession, telegram_id: int, role: str) -> User | None:
    """Assign/update user role."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.role = role
        await session.commit()
        await session.refresh(user)
    return user

async def create_student_request(
    session: AsyncSession,
    telegram_id: int,
    item_description: str,
    pickup_location: str,
    destination_school: str,
    delivery_date: str
) -> StudentRequest:
    """Save delivery request associated with the User."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    new_request = StudentRequest(
        user_id=user.id,
        item_description=item_description,
        pickup_location=pickup_location,
        destination_school=destination_school,
        delivery_date=delivery_date,
        status="pending"
    )
    session.add(new_request)
    await session.commit()
    await session.refresh(new_request)
    return new_request

