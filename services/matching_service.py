"""
Application Service: MatchingService

Owns all matching orchestration workflows:
- Triggering automatic chain discovery, persistence, and admin notification
- Listing pending trip_matches for admin review
- Approving a trip_match (updates DB + sends user notifications)
- Rejecting a trip_match (updates DB + sends user notifications)
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.db import async_session
from database.crud import (
    create_trip_match,
    get_pending_trip_matches,
    approve_trip_match as crud_approve_trip_match,
    reject_trip_match as crud_reject_trip_match,
)
from database.enums import MatchStatus, RequestStatus, TripStatus
from database.models import DeliveryRequest, DriverTrip, Location, TripMatch
from matching.engine import CandidateRequest, MatchingEngine
from matching.distance import get_distance_provider
from matching.distance_base import DistanceResult
from services.notifications import (
    notify_admin_trip_match,
    notify_student_approved,
    notify_driver_approved,
    notify_student_rejected,
    notify_driver_rejected,
)

logger = logging.getLogger(__name__)


class MatchingService:
    @staticmethod
    async def trigger_automatic_matching() -> int:
        provider = get_distance_provider()
        engine = MatchingEngine(provider=provider)
        created = 0

        async with async_session() as session:
            stmt = (
                select(DriverTrip)
                .where(DriverTrip.status == TripStatus.OPEN.value)
                .options(selectinload(DriverTrip.primary_location))
            )
            result = await session.execute(stmt)
            open_trips = list(result.scalars().all())

        for trip in open_trips:
            primary_loc = trip.primary_location
            if primary_loc is None:
                continue

            candidates = await MatchingService._filter_candidates(trip)
            if not candidates:
                continue

            chain = await engine.build_chain(
                primary_lat=primary_loc.lat,
                primary_lng=primary_loc.lng,
                candidates=candidates,
                max_stops=trip.max_stops,
            )
            if not chain:
                continue

            async with async_session() as session:
                persisted = []
                for stop in chain:
                    match = await create_trip_match(
                        session=session,
                        driver_trip_id=trip.id,
                        delivery_request_id=stop.delivery_request_id,
                        sequence_index=stop.sequence_index,
                        distance_from_previous_km=stop.distance_from_previous_km,
                        time_from_previous_min=stop.time_from_previous_min,
                    )
                    if match:
                        persisted.append(match)

                if persisted:
                    await notify_admin_trip_match(trip, persisted)
                    created += len(persisted)

        logger.info(f"MatchingService: {created} new trip_match(es) created and notified.")
        return created

    @staticmethod
    async def _filter_candidates(driver_trip: DriverTrip) -> list[CandidateRequest]:
        primary_loc = driver_trip.primary_location
        if primary_loc is None:
            return []

        provider = get_distance_provider()
        async with async_session() as session:
            stmt = (
                select(DeliveryRequest, Location)
                .join(Location, DeliveryRequest.location_id == Location.id)
                .where(
                    DeliveryRequest.direction == driver_trip.direction,
                    DeliveryRequest.travel_date == driver_trip.travel_date,
                    DeliveryRequest.status == RequestStatus.PENDING.value,
                    ~select(1)
                    .select_from(TripMatch)
                    .where(
                        TripMatch.driver_trip_id == driver_trip.id,
                        TripMatch.delivery_request_id == DeliveryRequest.id,
                        TripMatch.status.in_([
                            MatchStatus.PENDING_REVIEW.value,
                            MatchStatus.APPROVED.value,
                        ]),
                    )
                    .correlate(DeliveryRequest)
                    .exists(),
                )
                .order_by(DeliveryRequest.created_at.asc())
            )
            result = await session.execute(stmt)
            rows = result.all()

        candidates: list[CandidateRequest] = []
        for request, location in rows:
            distance_result = await provider.get_distance_and_time(
                primary_loc.lat,
                primary_loc.lng,
                location.lat,
                location.lng,
            )
            if distance_result.distance_km <= 8.0:
                candidates.append(
                    CandidateRequest(
                        delivery_request_id=request.id,
                        location_id=location.id,
                        lat=location.lat,
                        lng=location.lng,
                        item_description=request.item_description,
                        distance_result=distance_result,
                    )
                )

        candidates.sort(key=lambda c: c.distance_result.distance_km)
        return candidates

    @staticmethod
    async def get_pending_matches() -> list[TripMatch]:
        async with async_session() as session:
            return await get_pending_trip_matches(session)

    @staticmethod
    async def approve_match(match_id: int, admin_id: int) -> TripMatch | None:
        async with async_session() as session:
            match = await crud_approve_trip_match(session, match_id, admin_id=admin_id)

        if not match:
            return None

        student_telegram_id = match.delivery_request.user.telegram_id
        driver_telegram_id = match.driver_trip.user.telegram_id

        from matching.maps import build_student_maps_link, build_driver_maps_link
        from database.models import Location

        req_loc = match.delivery_request.location
        trip_loc = match.driver_trip.primary_location
        student_maps = build_student_maps_link(
            trip_loc.lat if trip_loc else 0.0,
            trip_loc.lng if trip_loc else 0.0,
            req_loc.lat if req_loc else 0.0,
            req_loc.lng if req_loc else 0.0,
        )

        trip_matches_stmt = (
            select(TripMatch)
            .where(TripMatch.driver_trip_id == match.driver_trip_id)
            .options(selectinload(TripMatch.delivery_request).selectinload(DeliveryRequest.location))
            .order_by(TripMatch.sequence_index.asc())
        )
        async with async_session() as session:
            trip_matches_result = await session.execute(trip_matches_stmt)
            trip_matches = list(trip_matches_result.scalars().all())

        waypoints = []
        for tm in trip_matches:
            loc = tm.delivery_request.location if tm.delivery_request else None
            if loc:
                waypoints.append(loc)

        driver_maps = build_driver_maps_link(
            trip_loc.lat if trip_loc else 0.0,
            trip_loc.lng if trip_loc else 0.0,
            waypoints[-1].lat if waypoints else 0.0,
            waypoints[-1].lng if waypoints else 0.0,
            waypoints=waypoints[1:-1] if len(waypoints) > 2 else [],
        )

        await notify_student_approved(student_telegram_id, maps_link=student_maps)
        await notify_driver_approved(driver_telegram_id, maps_link=driver_maps)

        logger.info(f"MatchingService: TripMatch#{match_id} approved by admin_id={admin_id}")
        return match

    @staticmethod
    async def reject_match(match_id: int, admin_id: int) -> TripMatch | None:
        async with async_session() as session:
            match = await crud_reject_trip_match(session, match_id, admin_id=admin_id)

        if not match:
            return None

        student_telegram_id = match.delivery_request.user.telegram_id
        driver_telegram_id = match.driver_trip.user.telegram_id

        await notify_student_rejected(student_telegram_id)
        await notify_driver_rejected(driver_telegram_id)

        logger.info(f"MatchingService: TripMatch#{match_id} rejected by admin_id={admin_id}")
        return match
