import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import ADMIN_IDS
from bot.keyboards.admin_keyboard import get_admin_keyboard
from database.models import Match

logger = logging.getLogger(__name__)

from bot.client import bot as _notification_bot


# ===== Retry Decorator =====

def _send_retry():
    """Retry decorator: 3 attempts with exponential backoff (1s, 2s, 4s)."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )


# ===== Internal Helpers =====

async def _send_message_with_retry(
    chat_id: int,
    text: str,
    message_type: str,
    parse_mode: str = "HTML",
    reply_markup=None,
) -> None:
    """
    Send a Telegram message with up to 3 retry attempts on failure.
    Logs user_id, message_type, and error details on final failure.
    """
    attempt = 0

    @_send_retry()
    async def _attempt():
        nonlocal attempt
        attempt += 1
        kwargs = dict(chat_id=chat_id, text=text, parse_mode=parse_mode)
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        await _notification_bot.send_message(**kwargs)

    try:
        await _attempt()
        logger.info(f"Notification sent: user_id={chat_id} type={message_type}")
    except Exception as e:
        logger.error(
            f"Notification failed after {attempt} attempt(s): "
            f"user_id={chat_id} message_type={message_type} error={e}"
        )


# ===== Admin Notifications =====

async def notify_admin_match(match: Match) -> None:
    """
    Send a match review card to all admin users with inline approve/reject buttons.
    Uses the match's eagerly-loaded relationships for display data.
    Checks if this student request had a previously rejected match and prepends a notice.
    """
    from database.db import async_session
    from sqlalchemy import select
    from database.enums import MatchStatus

    has_rejected_match = False
    async with async_session() as session:
        stmt = select(Match).where(
            Match.student_request_id == match.student_request_id,
            Match.status == MatchStatus.REJECTED.value
        )
        result = await session.execute(stmt)
        if result.scalars().first() is not None:
            has_rejected_match = True

    notice_prefix = ""
    if has_rejected_match:
        notice_prefix = (
            "⚠️ <b>Notice:</b> A new travel request matches the same student request "
            "that was previously rejected.\n\n"
        )

    review_text = (
        f"{notice_prefix}📋 <b>New Match Found</b>\n\n"
        f"<b>Match ID:</b> #{match.id}\n\n"
        "━━━ 🎓 Student Request ━━━\n"
        f"<b>Student:</b> {match.student_request.user.full_name or 'N/A'}\n"
        f"<b>Item:</b> {match.student_request.item_description}\n"
        f"<b>Pickup:</b> {match.student_request.pickup_location}\n"
        f"<b>School:</b> {match.student_request.destination_school}\n"
        f"<b>Date:</b> {match.student_request.delivery_date}\n\n"
        "━━━ 👨‍👩‍👧 Parent Travel ━━━\n"
        f"<b>Parent:</b> {match.parent_travel.user.full_name or 'N/A'}\n"
        f"<b>Origin:</b> {match.parent_travel.origin_location}\n"
        f"<b>School:</b> {match.parent_travel.destination_school}\n"
        f"<b>Date:</b> {match.parent_travel.travel_date}\n\n"
        "Please review this match:"
    )

    for admin_id in ADMIN_IDS:
        await _send_message_with_retry(
            chat_id=admin_id,
            text=review_text,
            message_type="admin_match_review",
            reply_markup=get_admin_keyboard(match.id),
        )


# ===== Student Notifications =====

async def notify_student_approved(telegram_id: int) -> None:
    """Notify the student that their delivery request has been matched and approved."""
    text = (
        "✅ <b>Great News!</b>\n\n"
        "Your delivery request has been matched with a traveler and approved by an admin.\n\n"
        "A parent/traveler will deliver your package. "
        "You will receive further updates soon."
    )
    await _send_message_with_retry(telegram_id, text, message_type="student_approved")


async def notify_student_rejected(telegram_id: int) -> None:
    """Notify the student that a potential match was rejected."""
    text = (
        "❌ <b>Match Update</b>\n\n"
        "A potential match for your delivery request was reviewed but not approved.\n\n"
        "Don't worry — we'll keep looking for available travelers. "
        "You'll be notified when a new match is found."
    )
    await _send_message_with_retry(telegram_id, text, message_type="student_rejected")


# ===== Parent Notifications =====

async def notify_parent_approved(telegram_id: int) -> None:
    """Notify the parent that their travel has been matched with a student request and approved."""
    text = (
        "✅ <b>Match Confirmed!</b>\n\n"
        "Your travel availability has been matched with a student delivery request "
        "and approved by an admin.\n\n"
        "You will be delivering a package on your upcoming trip. "
        "Further details will follow."
    )
    await _send_message_with_retry(telegram_id, text, message_type="parent_approved")


async def notify_parent_rejected(telegram_id: int) -> None:
    """Notify the parent that a potential match was rejected."""
    text = (
        "❌ <b>Match Update</b>\n\n"
        "A potential match involving your travel was reviewed but not approved.\n\n"
        "Your travel availability remains active. "
        "You'll be notified if another match is found."
    )
    await _send_message_with_retry(telegram_id, text, message_type="parent_rejected")
