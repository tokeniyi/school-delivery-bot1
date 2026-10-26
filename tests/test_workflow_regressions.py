"""Offline regressions for literal user text and canonical calendar dates."""
from html import escape
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers import admin, parent, student
from database.crud import (
    create_user, create_student_request, create_parent_travel,
    create_match, get_match_by_id,
)
from database.db import async_session
import services.notifications as notifications


PAYLOAD = "Books & <unknown> <b>literal</b>"


class FakeState:
    def __init__(self):
        self.data = dict(item_description=PAYLOAD, pickup_location="City",
                         origin_location="City", destination_school="School")
        self.cleared = False

    async def update_data(self, **values):
        self.data.update(values)

    async def get_data(self):
        return self.data.copy()

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self.cleared = True


class FakeSession:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return False


def message(text):
    return SimpleNamespace(text=text, from_user=SimpleNamespace(id=123456789),
                           answer=AsyncMock())


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "parent"])
async def test_accepted_dates_are_canonical(monkeypatch, role):
    module = student if role == "student" else parent
    state = FakeState()
    msg = message("2099-1-2")
    monkeypatch.setattr(module, "async_session", FakeSession)
    save = AsyncMock()
    monkeypatch.setattr(module, "create_student_request" if role == "student"
                        else "create_parent_travel", save)
    monkeypatch.setattr(module.MatchingService, "trigger_automatic_matching", AsyncMock())

    handler = student.process_delivery_date if role == "student" else parent.process_travel_date
    await handler(msg, state)
    key = "delivery_date" if role == "student" else "travel_date"
    assert state.data[key] == "2099-01-02"
    if role == "student":
        assert save.await_args.kwargs[key] == "2099-01-02"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "parent"])
async def test_submission_receipt_uses_plain_text(monkeypatch, role):
    module = student if role == "student" else parent
    state = FakeState()
    state.data["travel_date"] = "2099-01-02"
    msg = message("2099-01-02" if role == "student" else "✅ Yes")
    save = AsyncMock()
    monkeypatch.setattr(module, "async_session", FakeSession)
    monkeypatch.setattr(module, "create_student_request" if role == "student"
                        else "create_parent_travel", save)
    monkeypatch.setattr(module.MatchingService, "trigger_automatic_matching", AsyncMock())
    state.data["origin_location"] = PAYLOAD

    handler = student.process_delivery_date if role == "student" else parent.process_can_carry_packages
    await handler(msg, state)
    receipt = msg.answer.await_args
    assert PAYLOAD in receipt.args[0]
    # Bot defaults to HTML; explicitly disable parsing for literal receipt text.
    assert "parse_mode" in receipt.kwargs and receipt.kwargs["parse_mode"] is None
    assert state.cleared


@pytest.mark.asyncio
@pytest.mark.parametrize("channel", ["notification", "command"])
async def test_admin_cards_escape_all_user_fields(monkeypatch, fake_bot, channel):
    async with async_session() as session:
        await create_user(session, 910001, "student", PAYLOAD)
        await create_user(session, 910002, "parent", PAYLOAD)
        req = await create_student_request(session, 910001, PAYLOAD, PAYLOAD, PAYLOAD, PAYLOAD)
        trip = await create_parent_travel(session, 910002, PAYLOAD, PAYLOAD, PAYLOAD, True)
        match = await create_match(session, req.id, trip.id)
        loaded = await get_match_by_id(session, match.id)

    if channel == "notification":
        monkeypatch.setattr(notifications, "ADMIN_IDS", [123456789])
        await notifications.notify_admin_match(loaded)
        card = fake_bot.sent[0]["text"]
    else:
        monkeypatch.setattr(admin, "ADMIN_IDS", [123456789])
        msg = message("")
        await admin.cmd_admin_matches(msg)
        card = msg.answer.await_args.kwargs["text"]

    assert PAYLOAD not in card
    assert card.count(escape(PAYLOAD)) == 9
    assert "<b>" in card  # Keep the intended template formatting.
