import logging
from aiogram import Bot
from config import BOT_TOKEN, ADMIN_IDS
from bot.keyboards.admin_keyboard import get_admin_keyboard
from database.models import Match

logger = logging.getLogger(__name__)

# Shared bot instance for sending notifications outside of handler context
_notification_bot = Bot(token=BOT_TOKEN)


async def notify_admin_match(match: Match) -> None:
    """
    Send a match review card to all admin users with inline approve/reject buttons.
    Uses the match's eagerly-loaded relationships for display data.
    """
    review_text = (
        "📋 <b>New Match Found</b>\n\n"
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
        try:
            await _notification_bot.send_message(
                chat_id=admin_id,
                text=review_text,
                reply_markup=get_admin_keyboard(match.id),
                parse_mode="HTML"
            )
            logger.info(f"Sent match review notification to admin {admin_id} for Match#{match.id}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


async def notify_student_approved(telegram_id: int) -> None:
    """Notify the student that their delivery request has been matched and approved."""
    text = (
        "✅ <b>Great News!</b>\n\n"
        "Your delivery request has been matched with a traveler and approved by an admin.\n\n"
        "A parent/traveler will deliver your package. "
        "You will receive further updates soon."
    )
    try:
        await _notification_bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        logger.info(f"Sent approval notification to student {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to notify student {telegram_id}: {e}")


async def notify_parent_approved(telegram_id: int) -> None:
    """Notify the parent that their travel has been matched with a student request and approved."""
    text = (
        "✅ <b>Match Confirmed!</b>\n\n"
        "Your travel availability has been matched with a student delivery request "
        "and approved by an admin.\n\n"
        "You will be delivering a package on your upcoming trip. "
        "Further details will follow."
    )
    try:
        await _notification_bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        logger.info(f"Sent approval notification to parent {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to notify parent {telegram_id}: {e}")


async def notify_student_rejected(telegram_id: int) -> None:
    """Notify the student that a potential match was rejected."""
    text = (
        "❌ <b>Match Update</b>\n\n"
        "A potential match for your delivery request was reviewed but not approved.\n\n"
        "Don't worry — we'll keep looking for available travelers. "
        "You'll be notified when a new match is found."
    )
    try:
        await _notification_bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        logger.info(f"Sent rejection notification to student {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to notify student {telegram_id}: {e}")


async def notify_parent_rejected(telegram_id: int) -> None:
    """Notify the parent that a potential match was rejected."""
    text = (
        "❌ <b>Match Update</b>\n\n"
        "A potential match involving your travel was reviewed but not approved.\n\n"
        "Your travel availability remains active. "
        "You'll be notified if another match is found."
    )
    try:
        await _notification_bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        logger.info(f"Sent rejection notification to parent {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to notify parent {telegram_id}: {e}")
