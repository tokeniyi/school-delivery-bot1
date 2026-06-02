from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from database.db import async_session
from database.crud import create_user
from bot.keyboards.role_keyboard import get_role_keyboard

router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """This handler receives messages with the `/start` command, saves/updates the user, and presents the role selection keyboard."""
    telegram_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Asynchronously save or update the user
    async with async_session() as session:
        await create_user(
            session=session,
            telegram_id=telegram_id,
            username=username,
            full_name=full_name
        )

    welcome_text = (
        "Welcome to SchoolBridge 🚚\n\n"
        "Please select your role:"
    )
    await message.answer(
        text=welcome_text,
        reply_markup=get_role_keyboard()
    )

