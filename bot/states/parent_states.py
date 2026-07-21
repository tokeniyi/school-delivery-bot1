from aiogram.fsm.state import State, StatesGroup

class ParentTravelStates(StatesGroup):
    direction = State()
    location = State()
    travel_date = State()
