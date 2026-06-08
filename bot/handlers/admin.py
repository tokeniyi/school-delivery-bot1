import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS
from bot.keyboards.admin_keyboard import get_admin_keyboard
from services.matching_service import MatchingService
from services.health_service import HealthCheckService

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin_matches"))
async def cmd_admin_matches(message: Message) -> None:
    """Admin command to view all pending matches for review."""
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
        review_text = (
            f"<b>Match #{match.id}</b>\n\n"
            "🎓 <b>Student Request</b>\n"
            f"  Student: {match.student_request.user.full_name or 'N/A'}\n"
            f"  Item: {match.student_request.item_description}\n"
            f"  Pickup: {match.student_request.pickup_location}\n"
            f"  School: {match.student_request.destination_school}\n"
            f"  Date: {match.student_request.delivery_date}\n\n"
            "👨‍👩‍👧 <b>Parent Travel</b>\n"
            f"  Parent: {match.parent_travel.user.full_name or 'N/A'}\n"
            f"  Origin: {match.parent_travel.origin_location}\n"
            f"  School: {match.parent_travel.destination_school}\n"
            f"  Date: {match.parent_travel.travel_date}\n"
        )
        await message.answer(
            text=review_text,
            reply_markup=get_admin_keyboard(match.id),
            parse_mode="HTML"
        )


@router.message(Command("health"))
async def cmd_health(message: Message) -> None:
    """Admin-only health check: verifies database and Telegram API connectivity."""
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized /health access attempt by user_id={message.from_user.id}")
        await message.answer("⛔ Access denied.")
        return

    db_status = await HealthCheckService.check_database()
    telegram_status = await HealthCheckService.check_telegram()

    health_text = (
        "🩺 <b>System Health</b>\n\n"
        f"Database:     {db_status.display}\n"
        f"Telegram API: {telegram_status.display}\n"
        f"Application:  ✅ Running"
    )
    await message.answer(health_text, parse_mode="HTML")
    logger.info(
        f"Health check performed by admin_id={message.from_user.id}: "
        f"DB={db_status.display} TG={telegram_status.display}"
    )


@router.callback_query(F.data.startswith("approve_match_"))
async def callback_approve_match(callback: CallbackQuery) -> None:
    """Handle admin approval of a match via inline button."""
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
        parse_mode="HTML"
    )
    await callback.answer("Match approved!")

    logger.info(f"Match#{match_id} approved by admin {admin_id}")


@router.callback_query(F.data.startswith("reject_match_"))
async def callback_reject_match(callback: CallbackQuery) -> None:
    """Handle admin rejection of a match via inline button."""
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
        parse_mode="HTML"
    )
    await callback.answer("Match rejected.")

    logger.info(f"Match#{match_id} rejected by admin {admin_id}")
