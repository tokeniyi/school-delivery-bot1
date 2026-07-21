from aiogram.fsm.state import State, StatesGroup

class StudentRequestStates(StatesGroup):
    item_description = State()
    direction = State()
    location = State()
    delivery_date = State()
