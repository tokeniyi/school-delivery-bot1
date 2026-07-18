"""
Application Service: MatchingService

Owns all matching orchestration workflows:
- Triggering automatic match discovery, persistence, and admin notification
- Listing pending matches for admin review
- Approving a match (updates DB + sends user notifications)
- Rejecting a match (updates DB + sends user notifications)

Consolidates the duplicated matching loop that previously existed in both
student.py and parent.py handlers.

Interface Layer → MatchingService → matching.py / database.crud / notifications.py
"""

import logging

from database.db import async_session
from database.crud import (
    create_match,
    get_match_by_id,
    get_pending_matches,
    approve_match as crud_approve_match,
    reject_match as crud_reject_match,
)
from database.models import Match
from services.matching import find_matches
from services.notifications import (
    notify_admin_match,
    notify_student_approved,
    notify_parent_approved,
    notify_student_rejected,
    notify_parent_rejected,
)

logger = logging.getLogger(__name__)


class MatchingService:
    """
    Application service that owns all match-lifecycle orchestration.

    Single source of truth for the automatic matching loop, match review
    listing, and the approve/reject workflows. All interfaces (student handler,
    parent handler, admin handler) delegate to this service.
    """

    @staticmethod
    async def trigger_automatic_matching() -> int:
        """
        Run the automatic matching algorithm and persist any new matches.

        For every candidate pair returned by find_matches():
        - Attempts to persist a Match record (race-condition safe).
        - On success, loads the match with its relationships and notifies admins.

        Returns:
            The number of new matches successfully created and notified.

        Raises:
            Exception: Propagates unexpected errors so the calling handler can
                       present an appropriate fallback message to the user.
        """
        candidates = await find_matches()
        if not candidates:
            logger.info("MatchingService: no new candidates found.")
            return 0

        created = 0
        for req_id, trv_id in candidates:
            async with async_session() as session:
                new_match = await create_match(session, req_id, trv_id)
                if new_match:
                    loaded_match = await get_match_by_id(session, new_match.id)
                    if loaded_match:
                        await notify_admin_match(loaded_match)
                        created += 1
                else:
                    logger.warning(
                        f"MatchingService: duplicate match skipped Req#{req_id} ↔ Travel#{trv_id}"
                    )

        logger.info(f"MatchingService: {created} new match(es) created and notified.")
        return created

    @staticmethod
    async def get_pending_matches() -> list[Match]:
        """
        Return all matches currently awaiting admin review.

        Returns:
            A list of Match objects with eagerly-loaded student_request,
            parent_travel, and their respective user relationships.
        """
        async with async_session() as session:
            matches = await get_pending_matches(session)
        return matches

    @staticmethod
    async def approve_match(match_id: int, admin_id: int) -> Match | None:
        """
        Approve a pending match: persist status changes and notify both parties.

        Steps:
        1. Delegate DB update to database.crud.approve_match (sets statuses,
           records timestamp, writes audit log).
        2. Send approval notifications to the student and parent.

        Args:
            match_id: The ID of the match to approve.
            admin_id: The Telegram ID of the approving admin (for audit log).

        Returns:
            The approved Match record, or None if the match was not found or
            was not in pending_review status.
        """
        async with async_session() as session:
            match = await crud_approve_match(session, match_id, admin_id=admin_id)

        if not match:
            return None

        student_telegram_id = match.student_request.user.telegram_id
        parent_telegram_id = match.parent_travel.user.telegram_id

        await notify_student_approved(student_telegram_id)
        await notify_parent_approved(parent_telegram_id)

        logger.info(f"MatchingService: Match#{match_id} approved by admin_id={admin_id}")
        return match

    @staticmethod
    async def reject_match(match_id: int, admin_id: int) -> Match | None:
        """
        Reject a pending match: persist status changes and notify both parties.

        Steps:
        1. Delegate DB update to database.crud.reject_match (resets statuses,
           records timestamp, writes audit log).
        2. Send rejection notifications to the student and parent.

        Args:
            match_id: The ID of the match to reject.
            admin_id: The Telegram ID of the rejecting admin (for audit log).

        Returns:
            The rejected Match record, or None if the match was not found or
            was not in pending_review status.
        """
        async with async_session() as session:
            match = await crud_reject_match(session, match_id, admin_id=admin_id)

        if not match:
            return None

        student_telegram_id = match.student_request.user.telegram_id
        parent_telegram_id = match.parent_travel.user.telegram_id

        await notify_student_rejected(student_telegram_id)
        await notify_parent_rejected(parent_telegram_id)

        logger.info(f"MatchingService: Match#{match_id} rejected by admin_id={admin_id}")
        return match
