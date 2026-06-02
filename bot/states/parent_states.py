from aiogram.fsm.state import State, StatesGroup

class ParentTravelStates(StatesGroup):
    """FSM States Group for the guided parent/traveler travel availability flow."""
    origin_location = State()
    destination_school = State()
    travel_date = State()
    can_carry_packages = State()
