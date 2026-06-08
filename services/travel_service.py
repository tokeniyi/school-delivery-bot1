"""
Application Service: ParentTravelService

Owns the parent travel-schedule registration workflow.

Interface Layer → ParentTravelService → database.crud (Infrastructure Layer)
"""

import logging

from database.db import async_session
from database.crud import create_parent_travel
from database.models import ParentTravel

logger = logging.getLogger(__name__)


class ParentTravelService:
    """Application service that owns the parent travel registration workflow."""

    @staticmethod
    async def register_travel(
        telegram_id: int,
        origin_location: str,
        destination_school: str,
        travel_date: str,
        can_carry_packages: bool,
    ) -> ParentTravel:
        """
        Persist a new (or update an existing available) parent travel record.

        Called by the parent FSM handler after all fields are collected and
        validated at the Interface Layer.
        Delegates persistence to database.crud.create_parent_travel.

        Args:
            telegram_id: The parent's Telegram user ID.
            origin_location: Where the parent is traveling from.
            destination_school: The school the parent is traveling to.
            travel_date: Travel date as a YYYY-MM-DD string.
            can_carry_packages: Whether the parent can carry a package.

        Returns:
            The persisted ParentTravel record.
        """
        async with async_session() as session:
            travel = await create_parent_travel(
                session=session,
                telegram_id=telegram_id,
                origin_location=origin_location,
                destination_school=destination_school,
                travel_date=travel_date,
                can_carry_packages=can_carry_packages,
            )
        logger.debug(
            f"ParentTravelService.register_travel: telegram_id={telegram_id} "
            f"date={travel_date!r} can_carry={can_carry_packages}"
        )
        return travel
