import pytest
from bot.handlers.admin import cmd_admin_matches



class FakeMessage:
    def __init__(self, user_id):
        class U:
            def __init__(self, id):
                self.id = id
        self.from_user = U(user_id)
        self.answered = []

    async def answer(self, text, **kwargs):
        self.answered.append(text)


@pytest.mark.asyncio
async def test_admin_access_control():
    # non-admin
    fake_msg = FakeMessage(user_id=123456789)
    await cmd_admin_matches(fake_msg)
    assert any("Access denied" in t for t in fake_msg.answered)
