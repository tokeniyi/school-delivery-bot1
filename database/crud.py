from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.db import engine
from database.models import Base, User, StudentRequest, ParentTravel, Match

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

async def create_parent_travel(
    session: AsyncSession,
    telegram_id: int,
    origin_location: str,
    destination_school: str,
    travel_date: str,
    can_carry_packages: bool
) -> ParentTravel:
    """Save parent travel availability schedule."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    new_travel = ParentTravel(
        user_id=user.id,
        origin_location=origin_location,
        destination_school=destination_school,
        travel_date=travel_date,
        can_carry_packages=can_carry_packages,
        status="available"
    )
    session.add(new_travel)
    await session.commit()
    await session.refresh(new_travel)
    return new_travel

async def get_parent_travel(session: AsyncSession, telegram_id: int) -> list[ParentTravel]:
    """Retrieve all travel availability schedules submitted by a specific user."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return []
    stmt = select(ParentTravel).where(ParentTravel.user_id == user.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def update_parent_travel_status(session: AsyncSession, travel_id: int, status: str) -> ParentTravel | None:
    """Update status of a travel record."""
    stmt = select(ParentTravel).where(ParentTravel.id == travel_id)
    result = await session.execute(stmt)
    travel = result.scalar_one_or_none()
    if travel:
        travel.status = status
        await session.commit()
        await session.refresh(travel)
    return travel

# ===== Match CRUD Operations =====

async def match_exists(session: AsyncSession, request_id: int, travel_id: int) -> bool:
    """Check if a match between a specific request and travel already exists."""
    stmt = select(Match).where(
        Match.student_request_id == request_id,
        Match.parent_travel_id == travel_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None

async def create_match(session: AsyncSession, request_id: int, travel_id: int) -> Match:
    """Create a new potential match record."""
    new_match = Match(
        student_request_id=request_id,
        parent_travel_id=travel_id,
        status="pending_review"
    )
    session.add(new_match)
    await session.commit()
    await session.refresh(new_match)
    return new_match

async def get_pending_matches(session: AsyncSession) -> list[Match]:
    """Fetch all matches with status 'pending_review', eagerly loading related objects."""
    stmt = (
        select(Match)
        .where(Match.status == "pending_review")
        .options(
            selectinload(Match.student_request).selectinload(StudentRequest.user),
            selectinload(Match.parent_travel).selectinload(ParentTravel.user)
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_match_by_id(session: AsyncSession, match_id: int) -> Match | None:
    """Retrieve a specific match by ID with eager loading of related request, travel, and users."""
    stmt = (
        select(Match)
        .where(Match.id == match_id)
        .options(
            selectinload(Match.student_request).selectinload(StudentRequest.user),
            selectinload(Match.parent_travel).selectinload(ParentTravel.user)
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def approve_match(session: AsyncSession, match_id: int) -> Match | None:
    """Approve a match: set match to 'approved', student request to 'matched', parent travel to 'matched'."""
    match = await get_match_by_id(session, match_id)
    if not match:
        return None

    match.status = "approved"
    match.reviewed_at = datetime.utcnow()
    match.student_request.status = "matched"
    match.parent_travel.status = "matched"

    await session.commit()
    await session.refresh(match)
    return match

async def reject_match(session: AsyncSession, match_id: int) -> Match | None:
    """Reject a match: set match to 'rejected'. Request and travel remain unchanged."""
    match = await get_match_by_id(session, match_id)
    if not match:
        return None

    match.status = "rejected"
    match.reviewed_at = datetime.utcnow()

    await session.commit()
    await session.refresh(match)
    return match
