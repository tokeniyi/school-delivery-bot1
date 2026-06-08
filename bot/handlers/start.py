from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.role_keyboard import get_role_keyboard
from services.user_service import UserService

router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Receive /start, register or update the user, and present the role selection keyboard."""
    await UserService.register_or_update_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    welcome_text = (
        "Welcome to SchoolRelay 🚚\n\n"
        "Please select your role:"
    )
    await message.answer(
        text=welcome_text,
        reply_markup=get_role_keyboard()
    )
