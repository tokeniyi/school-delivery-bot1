import logging
from datetime import datetime, date
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database.db import async_session
from database.crud import update_user_role, create_delivery_request, get_or_create_location
from database.enums import Role
from bot.states.student_states import StudentRequestStates
from bot.keyboards.role_keyboard import STUDENT_BUTTON_TEXT
from bot.keyboards.direction_keyboard import get_direction_keyboard
from services.matching_service import MatchingService

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == STUDENT_BUTTON_TEXT)
async def student_role_selected(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    async with async_session() as session:
        await update_user_role(session, telegram_id, Role.STUDENT.value)
    await state.set_state(StudentRequestStates.item_description)
    await message.answer(
        "Let's create your delivery request.\n\n"
        "What item would you like delivered?"
    )


@router.message(StudentRequestStates.item_description)
async def process_item_description(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if not text or len(text) < 3:
        await message.answer(
            "Item description must be at least 3 characters long.\n"
            "What item would you like delivered?"
        )
        return
    if len(text) > 250:
        await message.answer(
            "Item description cannot exceed 250 characters.\n"
            "What item would you like delivered?"
        )
        return

    await state.update_data(item_description=text)
    await state.set_state(StudentRequestStates.direction)
    await message.answer(
        "Which direction is this delivery?\n\n",
        reply_markup=get_direction_keyboard(),
    )


@router.message(StudentRequestStates.direction)
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
    await state.set_state(StudentRequestStates.location)
    await message.answer(
        "Where in Lagos should the package be picked up / delivered to?\n\n"
        "Enter a landmark, address, or area name."
    )


@router.message(StudentRequestStates.location)
async def process_location(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if not text or len(text) < 2:
        await message.answer(
            "Location must be at least 2 characters long.\n"
            "Where in Lagos should the package be picked up / delivered to?"
        )
        return
    if len(text) > 100:
        await message.answer(
            "Location cannot exceed 100 characters.\n"
            "Where in Lagos should the package be picked up / delivered to?"
        )
        return

    await state.update_data(location=text)
    await state.set_state(StudentRequestStates.delivery_date)
    await message.answer(
        "What is your preferred delivery date?\n\n"
        "Example:\n"
        "2026-06-15"
    )


@router.message(StudentRequestStates.delivery_date)
async def process_delivery_date(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""

    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await message.answer(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2026-06-15).\n"
            "What is your preferred delivery date?"
        )
        return

    if parsed_date < date.today():
        await message.answer(
            "Delivery date cannot be in the past.\n"
            "What is your preferred delivery date?"
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
        await create_delivery_request(
            session=session,
            telegram_id=telegram_id,
            item_description=data["item_description"],
            direction=data["direction"],
            location=location,
            travel_date=parsed_date,
        )

    await state.clear()

    confirmation_text = (
        "✅ Request Submitted Successfully\n\n"
        f"Item:\n{data['item_description']}\n\n"
        f"Direction:\n{data['direction']}\n\n"
        f"Location:\n{data['location']}\n\n"
        f"Delivery Date:\n{text}\n\n"
        "Status:\nPending Review"
    )
    await message.answer(confirmation_text)

    try:
        await MatchingService.trigger_automatic_matching()
    except Exception as e:
        logger.error(f"Error during automatic matching: {e}", exc_info=True)
        await message.answer(
            "⚠️ Your request has been saved. An admin will review it shortly."
        )
