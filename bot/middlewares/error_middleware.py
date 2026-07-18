import logging
import traceback
from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update, TelegramObject

logger = logging.getLogger(__name__)

_USER_FACING_ERROR = (
    "⚠️ Something went wrong.\n\n"
    "Please try again later."
)


class ErrorMiddleware(BaseMiddleware):
    """
    Global error-catching middleware.

    Intercepts any unhandled exception raised inside a handler, logs the full
    traceback, and returns a safe user-facing error message instead of crashing
    the bot or silently swallowing the error.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            # Extract a useful identifier for log context
            update: Update | None = data.get("event_update")
            user_id: int | None = None
            if update:
                if update.message:
                    user_id = update.message.from_user.id if update.message.from_user else None
                elif update.callback_query:
                    user_id = update.callback_query.from_user.id

            logger.error(
                f"Unhandled exception for user_id={user_id}: {exc}\n"
                + traceback.format_exc()
            )

            # Attempt to send a safe error reply to the user
            try:
                if update and update.message:
                    await update.message.answer(_USER_FACING_ERROR)
                elif update and update.callback_query:
                    await update.callback_query.answer(
                        "Something went wrong. Please try again later.",
                        show_alert=True,
                    )
            except Exception as reply_exc:
                logger.error(f"Failed to send error reply to user_id={user_id}: {reply_exc}")
