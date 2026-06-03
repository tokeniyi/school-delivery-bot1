import logging
from datetime import datetime, date
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database.db import async_session
from database.crud import update_user_role, create_student_request, get_match_by_id, create_match
from bot.states.student_states import StudentRequestStates
from services.matching import find_matches
from services.notifications import notify_admin_match

logger = logging.getLogger(__name__)

router = Router()

@router.message(F.text.contains("Student"))
async def student_role_selected(message: Message, state: FSMContext) -> None:
    """Triggered when user selects the Student role. Saves the role and starts FSM."""
    telegram_id = message.from_user.id
    
    async with async_session() as session:
        await update_user_role(session, telegram_id, "student")
        
    await state.set_state(StudentRequestStates.item_description)
    await message.answer(
        "Let's create your delivery request.\n\n"
        "What item would you like delivered?"
    )

@router.message(StudentRequestStates.item_description)
async def process_item_description(message: Message, state: FSMContext) -> None:
    """Collects and validates the item description."""
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
    await state.set_state(StudentRequestStates.pickup_location)
    await message.answer("Where should the package be picked up?")

@router.message(StudentRequestStates.pickup_location)
async def process_pickup_location(message: Message, state: FSMContext) -> None:
    """Collects and validates the pickup location."""
    text = message.text.strip() if message.text else ""
    if not text or len(text) < 2:
        await message.answer(
            "Pickup location must be at least 2 characters long.\n"
            "Where should the package be picked up?"
        )
        return
    if len(text) > 100:
        await message.answer(
            "Pickup location cannot exceed 100 characters.\n"
            "Where should the package be picked up?"
        )
        return

    await state.update_data(pickup_location=text)
    await state.set_state(StudentRequestStates.destination_school)
    await message.answer("Which school should the item be delivered to?")

@router.message(StudentRequestStates.destination_school)
async def process_destination_school(message: Message, state: FSMContext) -> None:
    """Collects and validates the destination school."""
    text = message.text.strip() if message.text else ""
    if not text:
        await message.answer(
            "Destination school cannot be empty.\n"
            "Which school should the item be delivered to?"
        )
        return
    if len(text) > 100:
        await message.answer(
            "Destination school cannot exceed 100 characters.\n"
            "Which school should the item be delivered to?"
        )
        return

    await state.update_data(destination_school=text)
    await state.set_state(StudentRequestStates.delivery_date)
    await message.answer(
        "What is your preferred delivery date?\n\n"
        "Example:\n"
        "2026-06-15"
    )


@router.message(StudentRequestStates.delivery_date)
async def process_delivery_date(message: Message, state: FSMContext) -> None:
    """Collects, parses, and validates the preferred delivery date, then saves the request."""
    text = message.text.strip() if message.text else ""
    
    # 1. Parse date and check format (YYYY-MM-DD)
    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await message.answer(
            "Invalid date format. Please use YYYY-MM-DD (e.g. 2026-06-15).\n"
            "What is your preferred delivery date?"
        )
        return

    # 2. Check if the date is in the past
    if parsed_date < date.today():
        await message.answer(
            "Delivery date cannot be in the past.\n"
            "What is your preferred delivery date?"
        )
        return

    # Update date in state
    await state.update_data(delivery_date=text)

    # 3. Retrieve all FSM context data
    data = await state.get_data()
    telegram_id = message.from_user.id

    # 4. Save the request to the database
    async with async_session() as session:
        await create_student_request(
            session=session,
            telegram_id=telegram_id,
            item_description=data["item_description"],
            pickup_location=data["pickup_location"],
            destination_school=data["destination_school"],
            delivery_date=data["delivery_date"]
        )

    # 5. Clear FSM state context
    await state.clear()

    # 6. Send confirmation message
    confirmation_text = (
        "✅ Request Submitted Successfully\n\n"
        f"Item:\n{data['item_description']}\n\n"
        f"Pickup Location:\n{data['pickup_location']}\n\n"
        f"Destination:\n{data['destination_school']}\n\n"
        f"Delivery Date:\n{data['delivery_date']}\n\n"
        "Status:\nPending Review"
    )
    await message.answer(confirmation_text)

    # 7. Trigger automatic matching
    try:
        candidates = await find_matches()
        if not candidates:
            logger.info("No matching traveler found yet for this request")
            return
        
        for req_id, trv_id in candidates:
            async with async_session() as session:
                # Create match with race condition prevention
                new_match = await create_match(session, req_id, trv_id)
                if new_match:
                    # Load match with relationships for notification
                    loaded_match = await get_match_by_id(session, new_match.id)
                    if loaded_match:
                        await notify_admin_match(loaded_match)
                else:
                    logger.warning(f"Could not persist match (duplicate): Req#{req_id} ↔ Travel#{trv_id}")
    except Exception as e:
        logger.error(f"Error during automatic matching: {e}", exc_info=True)
        await message.answer(
            "⚠️ Your request has been saved. An admin will review it shortly."
        )
