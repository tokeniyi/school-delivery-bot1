import pytest

from bot.handlers.student import student_role_selected
from bot.handlers.parent import parent_role_selected
from bot.keyboards.role_keyboard import STUDENT_BUTTON_TEXT, PARENT_BUTTON_TEXT


class FakeState:
    def __init__(self):
        self.states = []

    async def set_state(self, state):
        self.states.append(state)

    async def update_data(self, **kwargs):
        return None

    async def get_data(self):
        return {}

    async def clear(self):
        return None


class FakeUser:
    def __init__(self, user_id: int = 1):
        self.id = user_id
        self.username = "tester"
        self.full_name = "Test User"


class FakeMessage:
    def __init__(self, text: str, user_id: int = 1):
        self.text = text
        self.from_user = FakeUser(user_id)
        self.answered = []

    async def answer(self, text, **kwargs):
        self.answered.append(text)


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_student_role_handler_uses_exact_keyboard_text(monkeypatch):
    calls = []

    async def fake_update_user_role(session, telegram_id, role):
        calls.append((telegram_id, role))

    monkeypatch.setattr("bot.handlers.student.update_user_role", fake_update_user_role)
    monkeypatch.setattr("bot.handlers.student.async_session", lambda: FakeSessionContext())

    state = FakeState()
    message = FakeMessage(STUDENT_BUTTON_TEXT)

    await student_role_selected(message, state)

    assert calls == [(1, "student")]
    assert state.states


@pytest.mark.asyncio
async def test_parent_role_handler_uses_exact_keyboard_text(monkeypatch):
    calls = []

    async def fake_update_user_role(session, telegram_id, role):
        calls.append((telegram_id, role))

    monkeypatch.setattr("bot.handlers.parent.update_user_role", fake_update_user_role)
    monkeypatch.setattr("bot.handlers.parent.async_session", lambda: FakeSessionContext())

    state = FakeState()
    message = FakeMessage(PARENT_BUTTON_TEXT)

    await parent_role_selected(message, state)

    assert calls == [(1, "parent")]
    assert state.states