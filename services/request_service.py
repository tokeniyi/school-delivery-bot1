"""
Application Service: StudentRequestService

Owns the student delivery-request registration workflow.

Interface Layer → StudentRequestService → database.crud (Infrastructure Layer)
"""

import logging

from database.db import async_session
from database.crud import create_student_request
from database.models import StudentRequest

logger = logging.getLogger(__name__)


class StudentRequestService:
    """Application service that owns the student request registration workflow."""

    @staticmethod
    async def register_request(
        telegram_id: int,
        item_description: str,
        pickup_location: str,
        destination_school: str,
        delivery_date: str,
    ) -> StudentRequest:
        """
        Persist a new (or update an existing pending) student delivery request.

        Called by the student FSM handler after all fields are collected and
        validated at the Interface Layer.
        Delegates persistence to database.crud.create_student_request.

        Args:
            telegram_id: The student's Telegram user ID.
            item_description: Description of the item to be delivered.
            pickup_location: Location from which the package should be collected.
            destination_school: Target school for delivery.
            delivery_date: Requested delivery date as a YYYY-MM-DD string.

        Returns:
            The persisted StudentRequest record.
        """
        async with async_session() as session:
            request = await create_student_request(
                session=session,
                telegram_id=telegram_id,
                item_description=item_description,
                pickup_location=pickup_location,
                destination_school=destination_school,
                delivery_date=delivery_date,
            )
        logger.debug(
            f"StudentRequestService.register_request: telegram_id={telegram_id} "
            f"date={delivery_date!r}"
        )
        return request
