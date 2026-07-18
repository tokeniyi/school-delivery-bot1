from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_yes_no_keyboard() -> ReplyKeyboardMarkup:
    """Returns a ReplyKeyboardMarkup with Yes and No selection buttons."""
    keyboard = [
        [
            KeyboardButton(text="✅ Yes"),
            KeyboardButton(text="❌ No")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )
