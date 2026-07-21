import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import ADMIN_IDS
from database.models import DriverTrip, TripMatch
from bot.keyboards.admin_keyboard import get_admin_keyboard
from matching.maps import build_student_maps_link, build_driver_maps_link

logger = logging.getLogger(__name__)

from bot.client import bot as _notification_bot


# ===== Retry Decorator =====


def _send_retry():
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


async def notify_admin_trip_match(
    driver_trip: DriverTrip,
    trip_matches: list[TripMatch],
) -> None:
    stops_text = ""
    for tm in trip_matches:
        req = tm.delivery_request
        loc = req.location if req else None
        dist = tm.distance_from_previous_km
        time = tm.time_from_previous_min
        stops_text += (
            f"\n<b>Stop {tm.sequence_index + 1}:</b> {req.item_description if req else 'N/A'}\n"
            f"  Location: {loc.raw_text if loc else 'N/A'}\n"
            f"  Distance: {dist:.1f} km" if dist is not None else "  Distance: N/A"
        )
        if time is not None:
            stops_text += f"\n  Time: {time:.0f} min"
        stops_text += "\n"

    review_text = (
        f"📋 <b>New Trip Match Found</b>\n\n"
        f"<b>Trip ID:</b> #{driver_trip.id}\n"
        f"<b>Driver:</b> {driver_trip.user.full_name or 'N/A'}\n"
        f"<b>Direction:</b> {driver_trip.direction}\n"
        f"<b>Date:</b> {driver_trip.travel_date}\n"
        f"<b>Stops:</b> {len(trip_matches)}\n"
        "━━━ Route Chain ━━━"
        f"{stops_text}"
        "\nPlease review each stop:"
    )

    for admin_id in ADMIN_IDS:
        await _send_message_with_retry(
            chat_id=admin_id,
            text=review_text,
            message_type="admin_trip_match_review",
        )


# ===== Student Notifications =====


async def notify_student_approved(telegram_id: int, maps_link: str | None = None) -> None:
    text = (
        "✅ <b>Great News!</b>\n\n"
        "Your delivery request has been matched with a driver and approved by an admin.\n\n"
    )
    if maps_link:
        text += f'<a href="{maps_link}">📍 View Route</a>\n\n'
    text += "A driver will deliver your package. You will receive further updates soon."
    await _send_message_with_retry(telegram_id, text, message_type="student_approved")


async def notify_student_rejected(telegram_id: int) -> None:
    text = (
        "❌ <b>Match Update</b>\n\n"
        "A potential match for your delivery request was reviewed but not approved.\n\n"
        "Don't worry — we'll keep looking for available drivers. "
        "You'll be notified when a new match is found."
    )
    await _send_message_with_retry(telegram_id, text, message_type="student_rejected")


# ===== Driver Notifications =====


async def notify_driver_approved(telegram_id: int, maps_link: str | None = None) -> None:
    text = (
        "✅ <b>Match Confirmed!</b>\n\n"
        "Your trip has been matched with student delivery requests and approved by an admin.\n\n"
    )
    if maps_link:
        text += f'<a href="{maps_link}">📍 Navigate Route</a>\n\n'
    text += "Please proceed with the scheduled stops in order."
    await _send_message_with_retry(telegram_id, text, message_type="driver_approved")


async def notify_driver_rejected(telegram_id: int) -> None:
    text = (
        "❌ <b>Match Update</b>\n\n"
        "A potential match involving your trip was reviewed but not approved.\n\n"
        "Your trip remains active. "
        "You'll be notified if another match is found."
    )
    await _send_message_with_retry(telegram_id, text, message_type="driver_rejected")
