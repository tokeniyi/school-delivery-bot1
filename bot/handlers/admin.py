import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS
from database.db import async_session
from database.crud import get_pending_matches, get_match_by_id, approve_match, reject_match
from bot.keyboards.admin_keyboard import get_admin_keyboard
from services.notifications import (
    notify_student_approved,
    notify_parent_approved,
    notify_student_rejected,
    notify_parent_rejected,
)

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin_matches"))
async def cmd_admin_matches(message: Message) -> None:
    """Admin command to view all pending matches for review."""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Access denied.")
        return

    async with async_session() as session:
        pending = await get_pending_matches(session)

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


@router.callback_query(F.data.startswith("approve_match_"))
async def callback_approve_match(callback: CallbackQuery) -> None:
    """Handle admin approval of a match via inline button."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Access denied.", show_alert=True)
        return

    # Extract match ID from callback data
    match_id = int(callback.data.replace("approve_match_", ""))

    async with async_session() as session:
        match = await approve_match(session, match_id)

    if not match:
        await callback.answer("❌ Match not found.", show_alert=True)
        return

    # Update the original message to reflect approval
    await callback.message.edit_text(
        text=f"✅ <b>Match #{match_id} Approved by Admin</b>",
        parse_mode="HTML"
    )
    await callback.answer("Match approved!")

    # Send notifications to student and parent
    student_telegram_id = match.student_request.user.telegram_id
    parent_telegram_id = match.parent_travel.user.telegram_id

    await notify_student_approved(student_telegram_id)
    await notify_parent_approved(parent_telegram_id)

    logger.info(f"Match#{match_id} approved by admin {callback.from_user.id}")


@router.callback_query(F.data.startswith("reject_match_"))
async def callback_reject_match(callback: CallbackQuery) -> None:
    """Handle admin rejection of a match via inline button."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Access denied.", show_alert=True)
        return

    # Extract match ID from callback data
    match_id = int(callback.data.replace("reject_match_", ""))

    async with async_session() as session:
        match = await reject_match(session, match_id)

    if not match:
        await callback.answer("❌ Match not found.", show_alert=True)
        return

    # Update the original message to reflect rejection
    await callback.message.edit_text(
        text=f"❌ <b>Match #{match_id} Rejected by Admin</b>",
        parse_mode="HTML"
    )
    await callback.answer("Match rejected.")

    # Send notifications to student and parent
    student_telegram_id = match.student_request.user.telegram_id
    parent_telegram_id = match.parent_travel.user.telegram_id

    await notify_student_rejected(student_telegram_id)
    await notify_parent_rejected(parent_telegram_id)

    logger.info(f"Match#{match_id} rejected by admin {callback.from_user.id}")
