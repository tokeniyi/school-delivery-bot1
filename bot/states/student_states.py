from aiogram.fsm.state import State, StatesGroup

class StudentRequestStates(StatesGroup):
    """FSM States Group for the guided student delivery request flow."""
    item_description = State()
    pickup_location = State()
    destination_school = State()
    delivery_date = State()
