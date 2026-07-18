"""
Application Service: UserService

Owns the User domain workflows:
- Registering or updating a user on first contact
- Setting a user's role

Interface Layer → UserService → database.crud (Infrastructure Layer)
"""

import logging

from database.db import async_session
from database.crud import create_user, update_user_role
from database.models import User

logger = logging.getLogger(__name__)


class UserService:
    """Application service that owns all User registration and role management workflows."""

    @staticmethod
    async def register_or_update_user(
        telegram_id: int,
        username: str | None,
        full_name: str | None,
    ) -> User:
        """
        Register a new user or update profile data for an existing one.

        Called by the /start handler when a user initiates a conversation.
        Delegates persistence to database.crud.create_user.

        Args:
            telegram_id: The Telegram user ID.
            username: The Telegram username (may be None).
            full_name: The Telegram display name (may be None).

        Returns:
            The persisted User record.
        """
        async with async_session() as session:
            user = await create_user(
                session=session,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
            )
        logger.debug(f"UserService.register_or_update_user: telegram_id={telegram_id}")
        return user

    @staticmethod
    async def set_user_role(telegram_id: int, role: str) -> User | None:
        """
        Assign or update the role for an existing user.

        Called by role-selection handlers (student.py, parent.py).
        Delegates persistence to database.crud.update_user_role.

        Args:
            telegram_id: The Telegram user ID.
            role: The role string to assign (e.g. "student", "parent").

        Returns:
            The updated User record, or None if the user does not exist.
        """
        async with async_session() as session:
            user = await update_user_role(session, telegram_id, role)
        logger.debug(f"UserService.set_user_role: telegram_id={telegram_id} role={role!r}")
        return user
