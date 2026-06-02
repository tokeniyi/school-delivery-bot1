import logging
from database.db import async_session
from database.crud import match_exists, create_match, get_pending_matches
from database.models import StudentRequest, ParentTravel
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def find_matches() -> list:
    """
    Find potential matches between pending student requests and available parent travels.

    Matching criteria:
    - pickup_location == origin_location (case-insensitive)
    - destination_school == destination_school (case-insensitive)
    - delivery_date == travel_date
    - parent.can_carry_packages == True

    Returns a list of newly created Match objects.
    """
    new_matches = []

    async with async_session() as session:
        # Fetch all pending student requests
        stmt_requests = select(StudentRequest).where(StudentRequest.status == "pending")
        result_requests = await session.execute(stmt_requests)
        pending_requests = list(result_requests.scalars().all())

        # Fetch all available parent travels that can carry packages
        stmt_travels = select(ParentTravel).where(
            ParentTravel.status == "available",
            ParentTravel.can_carry_packages == True
        )
        result_travels = await session.execute(stmt_travels)
        available_travels = list(result_travels.scalars().all())

        logger.info(
            f"Matching: {len(pending_requests)} pending requests, "
            f"{len(available_travels)} available travels"
        )

        # Compare each request against each travel
        for request in pending_requests:
            for travel in available_travels:
                # Case-insensitive comparison with stripped whitespace
                pickup_match = request.pickup_location.strip().lower() == travel.origin_location.strip().lower()
                school_match = request.destination_school.strip().lower() == travel.destination_school.strip().lower()
                date_match = request.delivery_date.strip() == travel.travel_date.strip()

                if pickup_match and school_match and date_match:
                    # Check if this match already exists
                    already_exists = await match_exists(session, request.id, travel.id)
                    if not already_exists:
                        new_match = await create_match(session, request.id, travel.id)
                        new_matches.append(new_match)
                        logger.info(
                            f"New match created: Match#{new_match.id} "
                            f"(Request#{request.id} <-> Travel#{travel.id})"
                        )

    logger.info(f"Matching complete. {len(new_matches)} new match(es) found.")
    return new_matches
