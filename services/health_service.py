"""
Application Service: HealthCheckService

Decouples infrastructure connectivity health checks from the Interface Layer.

Interface Layer → HealthCheckService → database.db / bot.client (Infrastructure)
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text

from database.db import async_session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthStatus:
    """Immutable result object for a single health check probe."""
    ok: bool
    label: str

    @property
    def display(self) -> str:
        return "✅ OK" if self.ok else "❌ FAIL"


class HealthCheckService:
    """
    Application service that owns all infrastructure connectivity probes.

    Decouples the /health command handler from the raw SQLAlchemy and aiogram
    API calls, in compliance with the Interface Layer restrictions defined in
    INSTRUCTIONS.md.
    """

    @staticmethod
    async def check_database() -> HealthStatus:
        """
        Probe the database connection by executing a lightweight SELECT 1 query.

        Returns:
            HealthStatus with ok=True if the DB is reachable, ok=False otherwise.
        """
        try:
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
            logger.debug("HealthCheckService.check_database: OK")
            return HealthStatus(ok=True, label="Database")
        except Exception as e:
            logger.error(f"HealthCheckService.check_database: FAIL — {e}")
            return HealthStatus(ok=False, label="Database")

    @staticmethod
    async def check_telegram() -> HealthStatus:
        """
        Probe the Telegram Bot API by calling getMe.

        Returns:
            HealthStatus with ok=True if the API is reachable, ok=False otherwise.
        """
        from bot.client import bot as _bot
        try:
            await _bot.get_me()
            logger.debug("HealthCheckService.check_telegram: OK")
            return HealthStatus(ok=True, label="Telegram API")
        except Exception as e:
            logger.error(f"HealthCheckService.check_telegram: FAIL — {e}")
            return HealthStatus(ok=False, label="Telegram API")
