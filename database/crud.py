import logging
from datetime import date, datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    AuditLog,
    DeliveryRequest,
    DriverTrip,
    Location,
    Match,
    TripMatch,
    User,
)
from database.enums import (
    GeocodeSource,
    MatchStatus,
    RequestStatus,
    Role,
    TripStatus,
)

logger = logging.getLogger(__name__)


# ===== Database Setup =====


async def create_tables():
    from database.db import engine
    from database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ===== User CRUD =====


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    full_name: str | None,
) -> User:
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
        role=Role.STUDENT.value,
    )
    session.add(new_user)
    await session.commit()
    logger.info(f"Created new user: telegram_id={telegram_id} full_name={full_name!r}")
    return new_user


async def update_user_role(
    session: AsyncSession, telegram_id: int, role: str
) -> User | None:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.role = role
        await session.commit()
    return user


# ===== Location CRUD =====


async def get_or_create_location(
    session: AsyncSession,
    raw_text: str,
    lat: float,
    lng: float,
    geocode_source: GeocodeSource = GeocodeSource.MANUAL,
) -> Location:
    stmt = select(Location).where(Location.raw_text == raw_text)
    result = await session.execute(stmt)
    location = result.scalar_one_or_none()
    if location:
        return location

    location = Location(
        raw_text=raw_text,
        lat=lat,
        lng=lng,
        geocode_source=geocode_source.value,
        resolved_at=datetime.now(timezone.utc),
    )
    session.add(location)
    await session.commit()
    logger.info(f"Created Location#{location.id}: {raw_text!r}")
    return location


# ===== DriverTrip CRUD =====


async def create_driver_trip(
    session: AsyncSession,
    telegram_id: int,
    direction: str,
    travel_date: date,
    primary_location: Location,
    max_stops: int = 4,
) -> DriverTrip:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    trip = DriverTrip(
        user_id=user.id,
        direction=direction,
        travel_date=travel_date,
        primary_location_id=primary_location.id,
        max_stops=max_stops,
        status=TripStatus.OPEN.value,
    )
    session.add(trip)
    await session.commit()
    logger.info(
        f"Created DriverTrip#{trip.id} for telegram_id={telegram_id} "
        f"direction={direction} date={travel_date}"
    )
    return trip


async def get_driver_trip_by_id(
    session: AsyncSession, trip_id: int
) -> DriverTrip | None:
    stmt = (
        select(DriverTrip)
        .where(DriverTrip.id == trip_id)
        .options(
            selectinload(DriverTrip.primary_location),
            selectinload(DriverTrip.trip_matches).selectinload(TripMatch.delivery_request),
            selectinload(DriverTrip.user),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ===== DeliveryRequest CRUD =====


async def create_delivery_request(
    session: AsyncSession,
    telegram_id: int,
    item_description: str,
    direction: str,
    location: Location,
    travel_date: date,
) -> DeliveryRequest:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist.")

    req = DeliveryRequest(
        user_id=user.id,
        item_description=item_description,
        direction=direction,
        location_id=location.id,
        travel_date=travel_date,
        status=RequestStatus.PENDING.value,
    )
    session.add(req)
    await session.commit()
    logger.info(
        f"Created DeliveryRequest#{req.id} for telegram_id={telegram_id} "
        f"direction={direction} date={travel_date}"
    )
    return req


async def get_delivery_request_by_id(
    session: AsyncSession, request_id: int
) -> DeliveryRequest | None:
    stmt = (
        select(DeliveryRequest)
        .where(DeliveryRequest.id == request_id)
        .options(
            selectinload(DeliveryRequest.location),
            selectinload(DeliveryRequest.user),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ===== TripMatch CRUD =====


async def create_trip_match(
    session: AsyncSession,
    driver_trip_id: int,
    delivery_request_id: int,
    sequence_index: int,
    distance_from_previous_km: float | None = None,
    time_from_previous_min: float | None = None,
) -> TripMatch | None:
    new_match = TripMatch(
        driver_trip_id=driver_trip_id,
        delivery_request_id=delivery_request_id,
        sequence_index=sequence_index,
        distance_from_previous_km=distance_from_previous_km,
        time_from_previous_min=time_from_previous_min,
        status=MatchStatus.PENDING_REVIEW.value,
    )
    session.add(new_match)
    try:
        await session.commit()
        logger.info(
            f"Created TripMatch#{new_match.id}: Trip#{driver_trip_id} ↔ Request#{delivery_request_id} "
            f"seq={sequence_index}"
        )
        return new_match
    except IntegrityError:
        await session.rollback()
        logger.warning(
            f"TripMatch already exists (race-safe skip): Trip#{driver_trip_id} ↔ Request#{delivery_request_id}"
        )
        return None


async def get_trip_match_by_id(
    session: AsyncSession, match_id: int
) -> TripMatch | None:
    stmt = (
        select(TripMatch)
        .where(TripMatch.id == match_id)
        .options(
            selectinload(TripMatch.driver_trip).selectinload(DriverTrip.primary_location),
            selectinload(TripMatch.driver_trip).selectinload(DriverTrip.user),
            selectinload(TripMatch.delivery_request).selectinload(DeliveryRequest.location),
            selectinload(TripMatch.delivery_request).selectinload(DeliveryRequest.user),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_pending_trip_matches(session: AsyncSession) -> list[TripMatch]:
    stmt = (
        select(TripMatch)
        .where(TripMatch.status == MatchStatus.PENDING_REVIEW.value)
        .options(
            selectinload(TripMatch.driver_trip).selectinload(DriverTrip.primary_location),
            selectinload(TripMatch.driver_trip).selectinload(DriverTrip.user),
            selectinload(TripMatch.delivery_request).selectinload(DeliveryRequest.location),
            selectinload(TripMatch.delivery_request).selectinload(DeliveryRequest.user),
        )
        .order_by(TripMatch.driver_trip_id.asc(), TripMatch.sequence_index.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def approve_trip_match(
    session: AsyncSession, match_id: int, admin_id: int | None = None
) -> TripMatch | None:
    try:
        match = await get_trip_match_by_id(session, match_id)
        if not match or match.status != MatchStatus.PENDING_REVIEW.value:
            return None

        match.status = MatchStatus.APPROVED.value
        match.reviewed_at = datetime.now(timezone.utc)
        match.delivery_request.status = RequestStatus.MATCHED.value

        if admin_id:
            audit = AuditLog(
                admin_id=admin_id,
                action="approve",
                entity_type="trip_match",
                entity_id=match_id,
                created_at=datetime.now(timezone.utc),
            )
            session.add(audit)

        await session.commit()
        logger.info(f"TripMatch#{match_id} approved by admin_id={admin_id}")
        return match
    except Exception:
        await session.rollback()
        raise


async def reject_trip_match(
    session: AsyncSession, match_id: int, admin_id: int | None = None
) -> TripMatch | None:
    try:
        match = await get_trip_match_by_id(session, match_id)
        if not match or match.status != MatchStatus.PENDING_REVIEW.value:
            return None

        match.status = MatchStatus.REJECTED.value
        match.reviewed_at = datetime.now(timezone.utc)
        match.delivery_request.status = RequestStatus.PENDING.value

        if admin_id:
            audit = AuditLog(
                admin_id=admin_id,
                action="reject",
                entity_type="trip_match",
                entity_id=match_id,
                created_at=datetime.now(timezone.utc),
            )
            session.add(audit)

        await session.commit()
        logger.info(f"TripMatch#{match_id} rejected by admin_id={admin_id}")
        return match
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
        logger.info(
            f"AuditLog#{entry.id}: admin={admin_id} action={action} {entity_type}#{entity_id}"
        )
        return entry
    except Exception:
        await session.rollback()
        raise
