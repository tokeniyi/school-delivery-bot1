import logging
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from database.db import async_session
from database.models import StudentRequest, ParentTravel, Match
from database.enums import RequestStatus, TravelStatus, MatchStatus

logger = logging.getLogger(__name__)


async def find_matches() -> list[tuple[int, int]]:
    """
    Optimized matcher using a single SQL JOIN query.

    Finds all (student_request_id, parent_travel_id) pairs that satisfy
    ALL matching conditions at the database level, with no Python-side loops
    over all records. Scales to 1000+ requests and travels efficiently.

    Conditions (enforced in SQL):
    - StudentRequest.status == PENDING
    - ParentTravel.status == AVAILABLE
    - ParentTravel.can_carry_packages == True
    - LOWER(TRIM(pickup_location)) == LOWER(TRIM(origin_location))
    - LOWER(TRIM(destination_school)) == LOWER(TRIM(destination_school))
    - TRIM(delivery_date) == TRIM(travel_date)
    - No existing Match with status IN (pending_review, approved) for this pair

    Returns:
        List of (student_request_id, parent_travel_id) tuples ready to be persisted.
    """
    async with async_session() as session:

        # Main JOIN query: students ✕ parents with all conditions applied in SQL
        stmt = (
            select(StudentRequest.id, ParentTravel.id)
            .join(
                ParentTravel,
                # Location match (case-insensitive, trimmed)
                (func.lower(func.trim(StudentRequest.pickup_location)) ==
                 func.lower(func.trim(ParentTravel.origin_location))) &
                # School match (case-insensitive, trimmed)
                (func.lower(func.trim(StudentRequest.destination_school)) ==
                 func.lower(func.trim(ParentTravel.destination_school))) &
                # Date match (exact after trim)
                (func.trim(StudentRequest.delivery_date) ==
                 func.trim(ParentTravel.travel_date))
            )
            .where(
                StudentRequest.status == RequestStatus.PENDING.value,
                ParentTravel.status == TravelStatus.AVAILABLE.value,
                ParentTravel.can_carry_packages.is_(True),
                # Exclude pairs that already have an active/pending match
                ~select(1)
                .select_from(Match)
                .where(
                    Match.student_request_id == StudentRequest.id,
                    Match.parent_travel_id == ParentTravel.id,
                    Match.status.in_([
                        MatchStatus.PENDING_REVIEW.value,
                        MatchStatus.APPROVED.value,
                    ])
                )
                .correlate(StudentRequest, ParentTravel)
                .exists()
            )
        )

        result = await session.execute(stmt)
        candidates = [(row[0], row[1]) for row in result.all()]

    count = len(candidates)
    if count:
        logger.info(f"Matching complete: {count} new candidate pair(s) found.")
    else:
        logger.info("Matching complete: no new candidates found.")

    return candidates