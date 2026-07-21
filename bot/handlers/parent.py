import logging
from datetime import datetime, date
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database.db import async_session
from database.crud import update_user_role, create_driver_trip, get_or_create_location
from database.enums import Role
from bot.states.parent_states import ParentTravelStates
from bot.keyboards.role_keyboard import DRIVER_BUTTON_TEXT
from bot.keyboards.direction_keyboard import get_direction_keyboard
from services.matching_service import MatchingService

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == DRIVER_BUTTON_TEXT)
async def driver_role_selected(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    async with async_session() as session:
        await update_user_role(session, telegram_id, Role.DRIVER.value)
    await state.set_state(ParentTravelStates.direction)
    await message.answer(
        "Let's register your upcoming trip.\n\n"
        "Which direction will you be traveling?",
        reply_markup=get_direction_keyboard(),
    )


@router.message(ParentTravelStates.direction)
async def process_direction(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if text not in ("CU → Lagos", "Lagos → CU"):
        await message.answer(
            "Please select a direction from the options below:",
            reply_markup=get_direction_keyboard(),
        )
        return

    direction = "outbound" if text == "CU → Lagos" else "inbound"
    await state.update_data(direction=direction)
    await state.set_state(ParentTravelStates.location)
    await message.answer(
        "What is your primary destination / origin in Lagos?\n\n"
        "Enter a landmark, address, or area name."
    )


@router.message(ParentTravelStates.location)
async def process_location(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if not text or len(text) < 2:
        await message.answer(
            "Location must be at least 2 characters long.\n"
            "What is your primary destination / origin in Lagos?"
        )
        return
    if len(text) > 100:
        await message.answer(
            "Location cannot exceed 100 characters.\n"
            "What is your primary destination / origin in Lagos?"
        )
        return

    await state.update_data(location=text)
    await state.set_state(ParentTravelStates.travel_date)
    await message.answer(
        "What is your travel date?\n\n"
        "Example:\n"
        "2026-06-20"
    )


@router.message(ParentTravelStates.travel_date)
async def process_travel_date(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""

    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await message.answer(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2026-06-20).\n"
            "What is your travel date?"
        )
        return

    if parsed_date < date.today():
        await message.answer(
            "Travel date cannot be in the past.\n"
            "What is your travel date?"
        )
        return

    data = await state.get_data()
    telegram_id = message.from_user.id

    mock_lat = 6.5244
    mock_lng = 3.3792
    async with async_session() as session:
        location = await get_or_create_location(
            session=session,
            raw_text=data["location"],
            lat=mock_lat,
            lng=mock_lng,
        )
        await create_driver_trip(
            session=session,
            telegram_id=telegram_id,
            direction=data["direction"],
            travel_date=parsed_date,
            primary_location=location,
        )

    await state.clear()

    confirmation_text = (
        "✅ Trip Submitted Successfully\n\n"
        f"Direction:\n{data['direction']}\n\n"
        f"Primary Location:\n{data['location']}\n\n"
        f"Travel Date:\n{text}\n\n"
        "Status:\nOpen for Matching"
    )
    await message.answer(confirmation_text)

    try:
        await MatchingService.trigger_automatic_matching()
    except Exception as e:
        logger.error(f"Error during automatic matching: {e}", exc_info=True)
        await message.answer(
            "⚠️ Your trip has been saved. Matching will begin shortly."
        )
