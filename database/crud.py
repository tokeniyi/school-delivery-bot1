import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import User, StudentRequest, ParentTravel, Match, AuditLog
from database.enums import RequestStatus, TravelStatus, MatchStatus

logger = logging.getLogger(__name__)


# ===== User CRUD =====

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Retrieve user record by Telegram ID."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None) -> User:
    """
    Insert new user if not exists; prevent duplicates.
    Updates username and full_name if the user already exists.
    Default role is 'Student'.
    """
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
        role="Student"
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    logger.info(f"Created new user: telegram_id={telegram_id} full_name={full_name!r}")
    return new_user


async def update_user_role(session: AsyncSession, telegram_id: int, role: str) -> User | None:
    """Assign or update a user's role (Student, Parent, Admin)."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.role = role
        await session.commit()
        await session.refresh(user)
    return user


# ===== Student Request CRUD =====

async def upsert_student_request(
    session: AsyncSession,
    telegram_id: int,
    item_description: str,
    pickup_location: str,
    destination_school: str,
    delivery_date: str,
) -> StudentRequest:
    """
    Upsert delivery request associated with a User.
    If a pending request exists, update it. Otherwise, create a new one.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    existing = await session.execute(
        select(StudentRequest).where(
            StudentRequest.user_id == user.id,
            StudentRequest.status == RequestStatus.PENDING.value
        )
    )
    student_request = existing.scalars().first()

    if student_request:
        student_request.item_description = item_description
        student_request.pickup_location = pickup_location
        student_request.destination_school = destination_school
        student_request.delivery_date = delivery_date
        await session.commit()
        await session.refresh(student_request)
        logger.info(f"Updated existing StudentRequest#{student_request.id} for telegram_id={telegram_id}")
        return student_request

    new_request = StudentRequest(
        user_id=user.id,
        item_description=item_description,
        pickup_location=pickup_location,
        destination_school=destination_school,
        delivery_date=delivery_date,
        status=RequestStatus.PENDING.value
    )
    session.add(new_request)
    await session.commit()
    await session.refresh(new_request)
    logger.info(
        f"Created new StudentRequest#{new_request.id} for telegram_id={telegram_id} "
        f"item={item_description!r} date={delivery_date}"
    )
    return new_request


async def create_student_request(
    session: AsyncSession,
    telegram_id: int,
    item_description: str,
    pickup_location: str,
    destination_school: str,
    delivery_date: str,
) -> StudentRequest:
    """
    Alias for compatibility with existing handlers.
    Delegates to upsert_student_request.
    """
    return await upsert_student_request(
        session, telegram_id, item_description,
        pickup_location, destination_school, delivery_date
    )


# ===== Parent Travel CRUD =====

async def upsert_parent_travel(
    session: AsyncSession,
    telegram_id: int,
    origin_location: str,
    destination_school: str,
    travel_date: str,
    can_carry_packages: bool,
) -> ParentTravel:
    """
    Upsert parent travel availability.
    If an available travel exists, update it. Otherwise, create a new one.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    existing = await session.execute(
        select(ParentTravel).where(
            ParentTravel.user_id == user.id,
            ParentTravel.status == TravelStatus.AVAILABLE.value
        )
    )
    parent_travel = existing.scalars().first()

    new_status = TravelStatus.AVAILABLE.value if can_carry_packages else TravelStatus.UNAVAILABLE.value

    if parent_travel:
        parent_travel.origin_location = origin_location
        parent_travel.destination_school = destination_school
        parent_travel.travel_date = travel_date
        parent_travel.can_carry_packages = can_carry_packages
        parent_travel.status = new_status
        await session.commit()
        await session.refresh(parent_travel)
        logger.info(f"Updated existing ParentTravel#{parent_travel.id} for telegram_id={telegram_id}")
        return parent_travel

    new_travel = ParentTravel(
        user_id=user.id,
        origin_location=origin_location,
        destination_school=destination_school,
        travel_date=travel_date,
        can_carry_packages=can_carry_packages,
        status=new_status
    )
    session.add(new_travel)
    await session.commit()
    await session.refresh(new_travel)
    logger.info(
        f"Created new ParentTravel#{new_travel.id} for telegram_id={telegram_id} "
        f"date={travel_date} can_carry={can_carry_packages}"
    )
    return new_travel


async def create_parent_travel(
    session: AsyncSession,
    telegram_id: int,
    origin_location: str,
    destination_school: str,
    travel_date: str,
    can_carry_packages: bool,
) -> ParentTravel:
    """
    Alias for compatibility with existing handlers.
    Delegates to upsert_parent_travel.
    """
    return await upsert_parent_travel(
        session, telegram_id, origin_location,
        destination_school, travel_date, can_carry_packages
    )


# ===== Match CRUD =====

async def match_exists(session: AsyncSession, request_id: int, travel_id: int) -> bool:
    """
    Check if an active match between a specific request and travel already exists.
    Only consider matches with status 'pending_review' or 'approved'.
    Ignore rejected matches so requests can be re-matched.
    """
    stmt = select(Match).where(
        Match.student_request_id == request_id,
        Match.parent_travel_id == travel_id,
        Match.status.in_([MatchStatus.PENDING_REVIEW.value, MatchStatus.APPROVED.value])
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def create_match(session: AsyncSession, request_id: int, travel_id: int) -> Match:
    """Create a new potential match record with status 'pending_review'."""
    new_match = Match(
        student_request_id=request_id,
        parent_travel_id=travel_id,
        status=MatchStatus.PENDING_REVIEW.value
    )
    session.add(new_match)
    await session.commit()
    await session.refresh(new_match)
    logger.info(f"Created Match#{new_match.id}: Request#{request_id} ↔ Travel#{travel_id}")
    return new_match


async def get_pending_matches(session: AsyncSession) -> list[Match]:
    """Fetch all matches with status 'pending_review', including related request and travel objects."""
    stmt = (
        select(Match)
        .where(Match.status == MatchStatus.PENDING_REVIEW.value)
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


async def approve_match(session: AsyncSession, match_id: int, admin_id: int | None = None) -> Match | None:
    """
    Approve a match:
    - Set match status to 'approved'
    - Set student request status to 'matched'
    - Set parent travel status to 'matched'
    - Record timezone-aware reviewed_at timestamp
    - Create audit log entry
    """
    match = await get_match_by_id(session, match_id)
    if not match or match.status != MatchStatus.PENDING_REVIEW.value:
        return None

    match.status = MatchStatus.APPROVED.value
    match.reviewed_at = datetime.now(timezone.utc)
    match.student_request.status = RequestStatus.MATCHED.value
    match.parent_travel.status = TravelStatus.MATCHED.value

    if admin_id:
        audit = AuditLog(
            admin_id=admin_id,
            action="approve",
            entity_type="match",
            entity_id=match_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(audit)

    await session.commit()
    await session.refresh(match)
    logger.info(f"Match#{match_id} approved by admin_id={admin_id}")
    return match


async def reject_match(session: AsyncSession, match_id: int, admin_id: int | None = None) -> Match | None:
    """
    Reject a match:
    - Set match status to 'rejected'
    - Reset student request status to 'pending' (so it can be re-matched)
    - Reset parent travel status to 'available'
    - Record timezone-aware reviewed_at timestamp
    - Create audit log entry
    """
    match = await get_match_by_id(session, match_id)
    if not match or match.status != MatchStatus.PENDING_REVIEW.value:
        return None

    match.status = MatchStatus.REJECTED.value
    match.reviewed_at = datetime.now(timezone.utc)
    match.student_request.status = RequestStatus.PENDING.value
    match.parent_travel.status = TravelStatus.AVAILABLE.value

    if admin_id:
        audit = AuditLog(
            admin_id=admin_id,
            action="reject",
            entity_type="match",
            entity_id=match_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(audit)

    await session.commit()
    await session.refresh(match)
    logger.info(f"Match#{match_id} rejected by admin_id={admin_id}")
    return match


# ===== Audit Log =====

async def create_audit_log(
    session: AsyncSession,
    admin_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
) -> AuditLog:
    """Create a standalone audit log entry for an admin action."""
    entry = AuditLog(
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    logger.info(f"AuditLog#{entry.id}: admin={admin_id} action={action} {entity_type}#{entity_id}")
    return entry