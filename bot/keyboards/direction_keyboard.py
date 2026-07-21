from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

DIRECTION_OUTBOUND = "CU → Lagos"
DIRECTION_INBOUND = "Lagos → CU"

def get_direction_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text=DIRECTION_OUTBOUND),
            KeyboardButton(text=DIRECTION_INBOUND),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
    )
