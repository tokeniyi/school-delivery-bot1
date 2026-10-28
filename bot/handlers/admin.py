from html import escape
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import text

from config import ADMIN_IDS
from database.db import async_session
from bot.keyboards.admin_keyboard import get_admin_keyboard
from bot.client import bot as _bot
from services.matching_service import MatchingService

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
            f"  Student: {escape(match.student_request.user.full_name or 'N/A')}\n"
            f"  Item: {escape(match.student_request.item_description)}\n"
            f"  Pickup: {escape(match.student_request.pickup_location)}\n"
            f"  School: {escape(match.student_request.destination_school)}\n"
            f"  Date: {escape(match.student_request.delivery_date)}\n\n"
            "👨‍👩‍👧 <b>Parent Travel</b>\n"
            f"  Parent: {escape(match.parent_travel.user.full_name or 'N/A')}\n"
            f"  Origin: {escape(match.parent_travel.origin_location)}\n"
            f"  School: {escape(match.parent_travel.destination_school)}\n"
            f"  Date: {escape(match.parent_travel.travel_date)}\n"
        )
        await message.answer(
            text=review_text,
            reply_markup=get_admin_keyboard(match.id, getattr(match, "review_revision", 1)),
            parse_mode="HTML"
        )


@router.message(Command("health"))
async def cmd_health(message: Message) -> None:
    """Admin-only health check: verifies database and Telegram API connectivity."""
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized /health access attempt by user_id={message.from_user.id}")
        await message.answer("⛔ Access denied.")
        return

    db_status = "❌ FAIL"
    telegram_status = "❌ FAIL"

    # Database connectivity check
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "✅ OK"
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")

    # Telegram API connectivity check
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
    """Handle admin approval of a match via inline button."""
    if callback.from_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized approve attempt by user_id={callback.from_user.id}")
        await callback.answer("⛔ Access denied.", show_alert=True)
        return

    try:
        parts = callback.data.removeprefix("approve_match_").split("_")
        if len(parts) not in (1, 2):
            raise ValueError
        match_id = int(parts[0])
        revision = int(parts[1]) if len(parts) == 2 else 1
    except (ValueError, TypeError):
        await callback.answer("Invalid match action.", show_alert=True)
        return
    admin_id = callback.from_user.id

    match = await MatchingService.approve_match(match_id, admin_id=admin_id, expected_revision=revision)

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

    try:
        parts = callback.data.removeprefix("reject_match_").split("_")
        if len(parts) not in (1, 2):
            raise ValueError
        match_id = int(parts[0])
        revision = int(parts[1]) if len(parts) == 2 else 1
    except (ValueError, TypeError):
        await callback.answer("Invalid match action.", show_alert=True)
        return
    admin_id = callback.from_user.id

    match = await MatchingService.reject_match(match_id, admin_id=admin_id, expected_revision=revision)

    if not match:
        await callback.answer("⚠️ This match has already been processed or does not exist.", show_alert=True)
        return

    await callback.message.edit_text(
        text=f"❌ <b>Match #{match_id} Rejected by Admin</b>",
        parse_mode="HTML"
    )
    await callback.answer("Match rejected.")

    logger.info(f"Match#{match_id} rejected by admin {admin_id}")


@router.message(Command("reconsider_match"))
async def cmd_reconsider_match(message: Message) -> None:
    """Explicit admin-only reconsideration; no automatic reopening by discovery."""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Access denied.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit() or int(parts[1]) < 1:
        await message.answer("Usage: /reconsider_match MATCH_ID", parse_mode=None)
        return
    match = await MatchingService.reconsider_match(int(parts[1]), message.from_user.id)
    if not match:
        await message.answer("Match cannot be reconsidered: it must be rejected and both records must remain eligible.", parse_mode=None)
        return
    await message.answer(f"Match #{match.id} reopened for admin review. Previous reviews are preserved.", parse_mode=None)
