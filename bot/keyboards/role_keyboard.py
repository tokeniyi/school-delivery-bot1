from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

STUDENT_BUTTON_TEXT = "🎓 Student"
PARENT_BUTTON_TEXT = "👨👩👧 Parent"

def get_role_keyboard() -> ReplyKeyboardMarkup:
    """Returns a ReplyKeyboardMarkup for selecting the user's role."""
    keyboard = [
        [
            KeyboardButton(text=STUDENT_BUTTON_TEXT),
            KeyboardButton(text=PARENT_BUTTON_TEXT)
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )
