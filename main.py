import asyncio
import logging
import logging.handlers
import os
import sys

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.client import bot
from bot.handlers.start import router as start_router
from bot.handlers.student import router as student_router
from bot.handlers.parent import router as parent_router
from bot.handlers.admin import router as admin_router
from bot.middlewares.error_middleware import ErrorMiddleware
from bot.middlewares.rate_limit_middleware import RateLimitMiddleware
from config import LOG_LEVEL, ENVIRONMENT, REDIS_URL

# 
# ===== Logging Setup =====

def setup_logging() -> None:
    """
    Configure structured logging:
    - RotatingFileHandler → logs/app.log (10 MB max, 5 backups)
    - StreamHandler → stdout console
    Both handlers share the same log format.
    """
    os.makedirs("logs", exist_ok=True)

    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Rotating file handler — 10 MB per file, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        filename="logs/app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


# ===== Application Entry Point =====

async def main() -> None:
    logger.info(
        f"SchoolBridge starting | environment={ENVIRONMENT} | log_level={LOG_LEVEL}"
    )

    # Redis FSM Storage
    if REDIS_URL is None:
        raise RuntimeError("REDIS_URL environment variable is not set")

    redis_client = Redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )

    storage = RedisStorage(redis=redis_client)

    # Create dispatcher
    dp = Dispatcher(storage=storage)

    # Register global middlewares
    dp.update.middleware(ErrorMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    # Register routers
    dp.include_router(start_router)
    dp.include_router(student_router)
    dp.include_router(parent_router)
    dp.include_router(admin_router)

    # Delete any stale webhook
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Application started successfully. Bot is now polling.")
    print("Bot is running...")

    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        await redis_client.close()
        logger.info("Application stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by operator.")
    except Exception as exc:
        logger.critical(f"Fatal error during startup: {exc}", exc_info=True)
        sys.exit(1)
