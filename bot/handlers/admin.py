import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import text

from config import ADMIN_IDS
from database.db import async_session
from services.matching_service import MatchingService
from bot.client import bot as _bot

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin_matches"))
async def cmd_admin_matches(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized /admin_matches access attempt by user_id={message.from_user.id}")
        await message.answer("⛔ Access denied.")
        return

    pending = await MatchingService.get_pending_matches()

    if not pending:
        await message.answer("📭 No pending matches to review.")
        return

    await message.answer(f"📋 <b>{len(pending)} Pending Match(es)</b>\n", parse_mode="HTML")

    for match in pending:
        req = match.delivery_request
        trip = match.driver_trip
        req_loc = req.location if req else None
        trip_loc = trip.primary_location if trip else None

        review_text = (
            f"<b>Match #{match.id}</b>\n\n"
            f"<b>Driver Trip:</b> #{trip.id} — {trip.user.full_name or 'N/A'}\n"
            f"  Direction: {trip.direction}\n"
            f"  Date: {trip.travel_date}\n"
            f"  Primary Location: {trip_loc.raw_text if trip_loc else 'N/A'}\n\n"
            f"<b>Stop {match.sequence_index + 1}:</b> {req.item_description}\n"
            f"  Student: {req.user.full_name or 'N/A'}\n"
            f"  Location: {req_loc.raw_text if req_loc else 'N/A'}\n"
            f"  Distance: {match.distance_from_previous_km:.1f} km" if match.distance_from_previous_km is not None else "  Distance: N/A"
        )
        if match.time_from_previous_min is not None:
            review_text += f"\n  Time: {match.time_from_previous_min:.0f} min"
        review_text += "\n\nPlease review this match:"

        from bot.keyboards.admin_keyboard import get_admin_keyboard
        await message.answer(
            text=review_text,
            reply_markup=get_admin_keyboard(match.id),
            parse_mode="HTML",
        )


@router.message(Command("health"))
async def cmd_health(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized /health access attempt by user_id={message.from_user.id}")
        await message.answer("⛔ Access denied.")
        return

    db_status = "❌ FAIL"
    telegram_status = "❌ FAIL"

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "✅ OK"
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")

    try:
        await _bot.get_me()
        telegram_status = "✅ OK"
    except Exception as e:
        logger.error(f"Health check Telegram API failure: {e}")

    health_text = (
        "🩺 <b>System Health</b>\n\n"
        f"Database:     {db_status}\n"
        f"Telegram API: {telegram_status}\n"
        f"Application:  ✅ Running"
    )
    await message.answer(health_text, parse_mode="HTML")
    logger.info(f"Health check performed by admin_id={message.from_user.id}: DB={db_status} TG={telegram_status}")


@router.callback_query(F.data.startswith("approve_match_"))
async def callback_approve_match(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized approve attempt by user_id={callback.from_user.id}")
        await callback.answer("⛔ Access denied.", show_alert=True)
        return

    match_id = int(callback.data.replace("approve_match_", ""))
    admin_id = callback.from_user.id

    match = await MatchingService.approve_match(match_id, admin_id=admin_id)

    if not match:
        await callback.answer("⚠️ This match has already been processed or does not exist.", show_alert=True)
        return

    await callback.message.edit_text(
        text=f"✅ <b>Match #{match_id} Approved by Admin</b>",
        parse_mode="HTML",
    )
    await callback.answer("Match approved!")
    logger.info(f"Match#{match_id} approved by admin {admin_id}")


@router.callback_query(F.data.startswith("reject_match_"))
async def callback_reject_match(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized reject attempt by user_id={callback.from_user.id}")
        await callback.answer("⛔ Access denied.", show_alert=True)
        return

    match_id = int(callback.data.replace("reject_match_", ""))
    admin_id = callback.from_user.id

    match = await MatchingService.reject_match(match_id, admin_id=admin_id)

    if not match:
        await callback.answer("⚠️ This match has already been processed or does not exist.", show_alert=True)
        return

    await callback.message.edit_text(
        text=f"❌ <b>Match #{match_id} Rejected by Admin</b>",
        parse_mode="HTML",
    )
    await callback.answer("Match rejected.")
    logger.info(f"Match#{match_id} rejected by admin {admin_id}")
