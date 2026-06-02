import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.crud import create_tables
from bot.handlers.start import router as start_router
from bot.handlers.student import router as student_router
from bot.handlers.parent import router as parent_router
from bot.handlers.admin import router as admin_router

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main() -> None:
    # 1. Initialize database tables
    logger.info("Initializing database...")
    await create_tables()
    logger.info("Database initialized successfully.")

    # 2. Create bot and dispatcher instances with FSM Memory Storage
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Register routers
    dp.include_router(start_router)
    dp.include_router(student_router)
    dp.include_router(parent_router)
    dp.include_router(admin_router)


    # 4. Start polling
    # Print the specific expected text for verification
    print("Bot is running...")
    logger.info("Starting Telegram bot polling...")
    
    # Delete webhook to prevent issues with previous webhook configurations
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

