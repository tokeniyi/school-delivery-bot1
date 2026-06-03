import logging
import time
from collections import defaultdict
from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)

# Configuration
_MAX_REQUESTS = 5        # maximum allowed requests
_WINDOW_SECONDS = 60     # per this many seconds
_RATE_LIMIT_REPLY = "⚠️ Too many requests. Please wait a moment before trying again."


class RateLimitMiddleware(BaseMiddleware):
    """
    In-memory sliding-window rate limiter.

    Allows up to MAX_REQUESTS messages per user per WINDOW_SECONDS.
    On limit breach, the handler is skipped and the user receives a
    throttle warning. State resets on bot restart (acceptable for pilot).
    """

    def __init__(self) -> None:
        super().__init__()
        # Maps user_id -> list of Unix timestamps for recent requests
        self._timestamps: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Only rate-limit Message events
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id: int | None = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        window_start = now - _WINDOW_SECONDS

        # Purge timestamps outside the current window
        history = self._timestamps[user_id]
        history[:] = [ts for ts in history if ts > window_start]

        if len(history) >= _MAX_REQUESTS:
            logger.warning(
                f"Rate limit hit: user_id={user_id} "
                f"sent {len(history)} requests in {_WINDOW_SECONDS}s"
            )
            await event.answer(_RATE_LIMIT_REPLY)
            return  # Skip handler

        history.append(now)
        return await handler(event, data)
