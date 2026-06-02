from datetime import datetime, date
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database.db import async_session
from database.crud import update_user_role, create_parent_travel
from bot.states.parent_states import ParentTravelStates
from bot.keyboards.yes_no_keyboard import get_yes_no_keyboard

router = Router()

@router.message(F.text.contains("Parent"))
async def parent_role_selected(message: Message, state: FSMContext) -> None:
    """Triggered when user selects the Parent role. Saves role to DB and starts Parent FSM."""
    telegram_id = message.from_user.id
    
    async with async_session() as session:
        await update_user_role(session, telegram_id, "parent")
        
    await state.set_state(ParentTravelStates.origin_location)
    await message.answer(
        "Let's register your upcoming trip.\n\n"
        "Where are you traveling from?"
    )

@router.message(ParentTravelStates.origin_location)
async def process_origin_location(message: Message, state: FSMContext) -> None:
    """Collects and validates the origin location."""
    text = message.text.strip() if message.text else ""
    if not text or len(text) < 2:
        await message.answer(
            "Origin location must be at least 2 characters long.\n"
            "Where are you traveling from?"
        )
        return

    await state.update_data(origin_location=text)
    await state.set_state(ParentTravelStates.destination_school)
    await message.answer("Which school are you traveling to?")

@router.message(ParentTravelStates.destination_school)
async def process_destination_school(message: Message, state: FSMContext) -> None:
    """Collects and validates the destination school."""
    text = message.text.strip() if message.text else ""
    if not text:
        await message.answer(
            "Destination school cannot be empty.\n"
            "Which school are you traveling to?"
        )
        return

    await state.update_data(destination_school=text)
    await state.set_state(ParentTravelStates.travel_date)
    await message.answer(
        "What is your travel date?\n\n"
        "Example:\n"
        "2026-06-20"
    )

@router.message(ParentTravelStates.travel_date)
async def process_travel_date(message: Message, state: FSMContext) -> None:
    """Collects, parses, and validates the travel date."""
    text = message.text.strip() if message.text else ""
    
    # 1. Parse date and check format (YYYY-MM-DD)
    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await message.answer(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2026-06-20).\n"
            "What is your travel date?"
        )
        return

    # 2. Check if the date is in the past
    if parsed_date < date.today():
        await message.answer(
            "Travel date cannot be in the past.\n"
            "What is your travel date?"
        )
        return

    await state.update_data(travel_date=text)
    await state.set_state(ParentTravelStates.can_carry_packages)
    await message.answer(
        "Are you available to carry a package for a student on this trip?",
        reply_markup=get_yes_no_keyboard()
    )

@router.message(ParentTravelStates.can_carry_packages)
async def process_can_carry_packages(message: Message, state: FSMContext) -> None:
    """Collects, maps availability string to Boolean, and saves the travel record."""
    text = message.text.strip() if message.text else ""
    
    if text not in ["✅ Yes", "❌ No"]:
        await message.answer(
            "Please select one of the options below:\n"
            "Are you available to carry a package for a student on this trip?",
            reply_markup=get_yes_no_keyboard()
        )
        return

    can_carry = True if text == "✅ Yes" else False
    display_availability = "Yes" if can_carry else "No"
    
    # Retrieve all FSM context data
    data = await state.get_data()
    telegram_id = message.from_user.id

    # Save travel availability to database
    async with async_session() as session:
        await create_parent_travel(
            session=session,
            telegram_id=telegram_id,
            origin_location=data["origin_location"],
            destination_school=data["destination_school"],
            travel_date=data["travel_date"],
            can_carry_packages=can_carry
        )

    # Clear FSM state context
    await state.clear()

    # Send confirmation message
    confirmation_text = (
        "✅ Travel Availability Submitted\n\n"
        f"Origin:\n{data['origin_location']}\n\n"
        f"Destination:\n{data['destination_school']}\n\n"
        f"Travel Date:\n{data['travel_date']}\n\n"
        f"Available For Deliveries:\n{display_availability}\n\n"
        "Status:\nAvailable"
    )
    await message.answer(confirmation_text)
