from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_role_keyboard() -> ReplyKeyboardMarkup:
    """Returns a ReplyKeyboardMarkup for selecting the user's role."""
    keyboard = [
        [
            KeyboardButton(text="🎓 Student"),
            KeyboardButton(text="👨👩👧 Parent")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )
