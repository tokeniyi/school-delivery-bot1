import logging
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import User, StudentRequest, ParentTravel, Match, MatchEvent, AuditLog
from database.enums import RequestStatus, TravelStatus, MatchStatus, Role
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ===== Database Setup =====

async def create_tables():
    """Create all database tables from models."""
    from database.db import engine
    from database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
        role=Role.STUDENT.value
    )
    session.add(new_user)
    await session.commit()
    logger.info(f"Created new user: telegram_id={telegram_id} full_name={full_name!r}")
    return new_user


async def update_user_role(session: AsyncSession, telegram_id: int, role: str) -> User | None:
    """Assign or update a user's role (Student, Parent, Admin)."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.role = role
        await session.commit()
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
    Update an unreviewed pending draft; version edits with candidate history.
    Approved records are preserved and new submissions create new rows.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    await _lock_users(session, [user.id])
    existing = await session.scalars(
        select(StudentRequest).where(
            StudentRequest.user_id == user.id,
            StudentRequest.status == RequestStatus.PENDING.value,
            ~select(Match.id).where(Match.student_request_id == StudentRequest.id,
                                    Match.status == MatchStatus.APPROVED.value).exists(),
        ).execution_options(populate_existing=True)
    )
    drafts = existing.all()
    if len(drafts) > 1:
        await session.rollback()
        raise ValueError("Multiple pending requests: explicit record selection is required")
    student_request = drafts[0] if drafts else None

    try:
        if student_request and (
            student_request.item_description, student_request.pickup_location,
            student_request.destination_school, student_request.delivery_date
        ) != (item_description, pickup_location, destination_school, delivery_date):
            if await _supersede_reviewed_source(session, student_request, "request"):
                student_request = None
        if student_request:
            student_request.item_description = item_description
            student_request.pickup_location = pickup_location
            student_request.destination_school = destination_school
            student_request.delivery_date = delivery_date
            await session.commit()
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
        logger.info(
            f"Created new StudentRequest#{new_request.id} for telegram_id={telegram_id} "
            f"item={item_description!r} date={delivery_date}"
        )
        return new_request
    except Exception:
        await session.rollback()
        raise


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
    Update an unreviewed available draft; version edits with candidate history.
    Approved records are preserved and new submissions create new rows.
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    await _lock_users(session, [user.id])
    existing = await session.scalars(
        select(ParentTravel).where(
            ParentTravel.user_id == user.id,
            ParentTravel.status == TravelStatus.AVAILABLE.value,
            ~select(Match.id).where(Match.parent_travel_id == ParentTravel.id,
                                    Match.status == MatchStatus.APPROVED.value).exists(),
        ).execution_options(populate_existing=True)
    )
    drafts = existing.all()
    if len(drafts) > 1:
        await session.rollback()
        raise ValueError("Multiple available travels: explicit record selection is required")
    parent_travel = drafts[0] if drafts else None

    new_status = TravelStatus.AVAILABLE.value if can_carry_packages else TravelStatus.UNAVAILABLE.value

    try:
        if parent_travel and (
            parent_travel.origin_location, parent_travel.destination_school,
            parent_travel.travel_date, parent_travel.can_carry_packages
        ) != (origin_location, destination_school, travel_date, can_carry_packages):
            if await _supersede_reviewed_source(session, parent_travel, "travel"):
                parent_travel = None
        if parent_travel:
            parent_travel.origin_location = origin_location
            parent_travel.destination_school = destination_school
            parent_travel.travel_date = travel_date
            parent_travel.can_carry_packages = can_carry_packages
            parent_travel.status = new_status
            await session.commit()
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
        logger.info(
            f"Created new ParentTravel#{new_travel.id} for telegram_id={telegram_id} "
            f"date={travel_date} can_carry={can_carry_packages}"
        )
        return new_travel
    except Exception:
        await session.rollback()
        raise


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

async def _lock_users(session: AsyncSession, user_ids) -> None:
    """One lock order for submission, candidate creation, review and reconsideration.

    Owner locks also cover insertion when a user has no active draft row yet.
    They serialize workflows sharing a resource without a global lifecycle lock.
    """
    for user_id in sorted(set(user_ids)):
        await session.execute(select(User.id).where(User.id == user_id).with_for_update())


async def _lock_pair(session: AsyncSession, request_id: int, travel_id: int):
    owners = (await session.execute(
        select(StudentRequest.user_id, ParentTravel.user_id)
        .select_from(StudentRequest).join(ParentTravel, ParentTravel.id == travel_id)
        .where(StudentRequest.id == request_id)
    )).first()
    if not owners:
        return None, None
    await _lock_users(session, owners)
    req = await session.get(StudentRequest, request_id, populate_existing=True)
    travel = await session.get(ParentTravel, travel_id, populate_existing=True)
    return req, travel


def _eligible(req, travel) -> bool:
    return bool(req and travel and req.status == RequestStatus.PENDING.value
                and travel.status == TravelStatus.AVAILABLE.value
                and travel.can_carry_packages
                and req.pickup_location.strip().lower() == travel.origin_location.strip().lower()
                and req.destination_school.strip().lower() == travel.destination_school.strip().lower()
                and req.delivery_date.strip() == travel.travel_date.strip())


def _event(session, match, previous, actor_id, reason):
    session.add(MatchEvent(match_id=match.id, from_status=previous,
                           to_status=match.status, actor_id=actor_id, reason=reason))


async def _supersede_reviewed_source(session, source, kind):
    """Keep reviewed details stable; edits replace a source with candidate history.

    Caller holds the source owner's lock. No admin rejection is fabricated.
    Lock candidate rows in ID order, the same order used by approval closure.
    """
    column = Match.student_request_id if kind == "request" else Match.parent_travel_id
    rows = (await session.scalars(select(Match).where(column == source.id)
                                 .order_by(Match.id).with_for_update()
                                 .execution_options(populate_existing=True))).all()
    if not rows:
        return False
    if any(m.status == MatchStatus.APPROVED.value for m in rows):
        raise ValueError("Cannot edit an approved source")
    source.status = (RequestStatus.SUPERSEDED.value if kind == "request"
                     else TravelStatus.SUPERSEDED.value)
    for match in rows:
        if match.status == MatchStatus.PENDING_REVIEW.value:
            match.status = MatchStatus.CLOSED.value
            match.closure_reason = f"source_edited:{kind}:{source.id}"
            match.reviewed_at = datetime.now(timezone.utc)
            _event(session, match, MatchStatus.PENDING_REVIEW.value,
                   None, match.closure_reason)
    return True


async def create_match(session: AsyncSession, request_id: int, travel_id: int) -> Match | None:
    """Revalidate discovery under owner locks; never reopen a considered pair."""
    try:
        req, travel = await _lock_pair(session, request_id, travel_id)
        exists = await session.scalar(select(Match.id).where(
            Match.student_request_id == request_id, Match.parent_travel_id == travel_id))
        if not _eligible(req, travel) or exists:
            await session.rollback()
            return None
        match = Match(student_request_id=request_id, parent_travel_id=travel_id,
                      status=MatchStatus.PENDING_REVIEW.value)
        session.add(match)
        await session.flush()
        _event(session, match, None, None, "candidate_created")
        await session.commit()
        return match
    except IntegrityError as exc:
        await session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            return None
        raise
    except Exception:
        await session.rollback()
        raise


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
    result = await session.execute(stmt.execution_options(populate_existing=True))
    return result.scalar_one_or_none()


async def _review(session, match_id, admin_id, *, approve, expected_revision=None):
    try:
        pair = (await session.execute(select(Match.student_request_id, Match.parent_travel_id)
                                      .where(Match.id == match_id))).first()
        if not pair:
            await session.rollback()
            return None
        req, travel = await _lock_pair(session, *pair)
        # Two otherwise independent allocations may close the same crossed candidate.
        # Lock all affected candidate rows in ID order before changing any of them.
        neighborhood = (await session.scalars(select(Match).where(or_(
            Match.student_request_id == pair[0], Match.parent_travel_id == pair[1]
        )).order_by(Match.id).with_for_update()
            .execution_options(populate_existing=True))).all()
        match = next(m for m in neighborhood if m.id == match_id)
        if (match.status != MatchStatus.PENDING_REVIEW.value
                or (expected_revision is not None and match.review_revision != expected_revision)):
            await session.rollback()
            return None
        if approve and not _eligible(req, travel):
            await session.rollback()
            return None
        previous = match.status
        match.status = MatchStatus.APPROVED.value if approve else MatchStatus.REJECTED.value
        match.reviewed_at = datetime.now(timezone.utc)
        _event(session, match, previous, admin_id, "admin_approval" if approve else "admin_rejection")
        if approve:
            req.status = RequestStatus.MATCHED.value
            travel.status = TravelStatus.MATCHED.value
            for other in neighborhood:
                if other.id != match.id and other.status == MatchStatus.PENDING_REVIEW.value:
                    other.status = MatchStatus.CLOSED.value
                    other.reviewed_at = match.reviewed_at
                    other.closure_reason = f"allocated_by_match:{match.id}"
                    _event(session, other, MatchStatus.PENDING_REVIEW.value,
                           admin_id, other.closure_reason)
                    if admin_id:
                        session.add(AuditLog(admin_id=admin_id, action="auto_close",
                                             entity_type="match", entity_id=other.id))
        # Rejection never owns an allocation: do not reset shared resource state.
        if admin_id:
            session.add(AuditLog(admin_id=admin_id, action="approve" if approve else "reject",
                                 entity_type="match", entity_id=match.id))
        await session.commit()
        return await get_match_by_id(session, match.id)
    except Exception:
        await session.rollback()
        raise


async def approve_match(session: AsyncSession, match_id: int, admin_id: int | None = None,
                        *, expected_revision: int | None = None) -> Match | None:
    """Atomically allocate a request/trip and close incompatible candidates."""
    return await _review(session, match_id, admin_id, approve=True,
                         expected_revision=expected_revision)


async def reject_match(session: AsyncSession, match_id: int, admin_id: int | None = None,
                       *, expected_revision: int | None = None) -> Match | None:
    """Record a rejection without releasing resources held by another approval."""
    return await _review(session, match_id, admin_id, approve=False,
                         expected_revision=expected_revision)


async def reconsider_match(session: AsyncSession, match_id: int, admin_id: int) -> Match | None:
    """Explicit configured-admin reopen; retain every prior review in match_events."""
    from config import ADMIN_IDS
    if admin_id not in ADMIN_IDS:
        raise PermissionError("Only configured admins may reconsider rejected matches")
    try:
        pair = (await session.execute(select(Match.student_request_id, Match.parent_travel_id)
                                      .where(Match.id == match_id))).first()
        if not pair:
            await session.rollback()
            return None
        req, travel = await _lock_pair(session, *pair)
        match = await session.get(Match, match_id, populate_existing=True, with_for_update=True)
        if match.status != MatchStatus.REJECTED.value or not _eligible(req, travel):
            await session.rollback()
            return None
        match.status = MatchStatus.PENDING_REVIEW.value
        match.reviewed_at = None
        match.review_revision += 1
        _event(session, match, MatchStatus.REJECTED.value, admin_id, "explicit_reconsideration")
        session.add(AuditLog(admin_id=admin_id, action="reconsider", entity_type="match", entity_id=match.id))
        await session.commit()
        return await get_match_by_id(session, match.id)
    except Exception:
        await session.rollback()
        raise


# ===== Audit Log =====

async def create_audit_log(
    session: AsyncSession,
    admin_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
) -> AuditLog:
    """Create a standalone audit log entry for an admin action."""
    try:
        entry = AuditLog(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(entry)
        await session.commit()
        logger.info(f"AuditLog#{entry.id}: admin={admin_id} action={action} {entity_type}#{entity_id}")
        return entry
    except Exception:
        await session.rollback()
        raise
