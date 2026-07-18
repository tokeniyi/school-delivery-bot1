from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_keyboard(match_id: int) -> InlineKeyboardMarkup:
    """Returns an InlineKeyboardMarkup with Approve and Reject buttons for a match."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Approve",
                    callback_data=f"approve_match_{match_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=f"reject_match_{match_id}"
                )
            ]
        ]
    )
    return keyboard
