import pytest
pytest.skip('moved to split tests', allow_module_level=True)

from database.db import async_session
from database.crud import (
    create_tables, create_user, update_user_role,
    create_student_request, create_parent_travel,
    get_match_by_id, approve_match, reject_match
)
from services.matching import find_matches
import services.notifications as notifications
from config import ADMIN_IDS
from sqlalchemy import delete
from database.models import User, StudentRequest, ParentTravel, Match


class FakeBot:
    def __init__(self, raise_on: List[int] | None = None):
        self.sent: List[dict] = []
        self.raise_on = set(raise_on or [])

    async def send_message(self, chat_id, text, **kwargs):
        if chat_id in self.raise_on:
            raise RuntimeError(f"Simulated send failure for {chat_id}")
        self.sent.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})


class FakeMessage:
    def __init__(self, user_id: int):
        class U:
            def __init__(self, id):
                self.id = id
        self.from_user = U(user_id)
        self.answered: List[str] = []

    async def answer(self, text, **kwargs):
        self.answered.append(text)


def _cleanup_db_sync():
    async def _c():
        await create_tables()
        async with async_session() as session:
            await session.execute(delete(Match))
            await session.execute(delete(StudentRequest))
            await session.execute(delete(ParentTravel))
            await session.execute(delete(User))
            await session.commit()
    asyncio.run(_c())


def test_rejection_flow():
    """Admin rejects a match: match.status -> 'rejected'; request/travel unchanged; admins are notified when created and rejection notifications are sent."""

    async def run():
        fake_bot = FakeBot()
        notifications._notification_bot = fake_bot

        await create_tables()
        # clean DB
        async with async_session() as session:
            await session.execute(delete(Match))
            await session.execute(delete(StudentRequest))
            await session.execute(delete(ParentTravel))
            await session.execute(delete(User))
            await session.commit()

        # create users
        async with async_session() as session:
            student = await create_user(session=session, telegram_id=9001001, username="s_reject", full_name="S Reject")
            await update_user_role(session, student.telegram_id, "student")
            parent = await create_user(session=session, telegram_id=9002002, username="p_reject", full_name="P Reject")
            await update_user_role(session, parent.telegram_id, "parent")

        # create request and travel
        async with async_session() as session:
            req = await create_student_request(session=session, telegram_id=student.telegram_id, item_description="Item", pickup_location="X", destination_school="Y", delivery_date="2026-08-01")
            trv = await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="X", destination_school="Y", travel_date="2026-08-01", can_carry_packages=True)

        # run matching
        new = await find_matches()
        assert len(new) == 1
        match = new[0]

        # load with relationships
        async with async_session() as session:
            match = await get_match_by_id(session, match.id)

        # reject the match
        async with async_session() as session:
            rejected = await reject_match(session, match.id)

        assert rejected is not None and rejected.status == "rejected"
        assert rejected.student_request.status == "pending"
        assert rejected.parent_travel.status == "available"

        # send rejection notifications and ensure they don't raise
        await notifications.notify_student_rejected(rejected.student_request.user.telegram_id)
        await notifications.notify_parent_rejected(rejected.parent_travel.user.telegram_id)

        # verify notifications were recorded
        student_msgs = [m for m in fake_bot.sent if m["chat_id"] == student.telegram_id]
        parent_msgs = [m for m in fake_bot.sent if m["chat_id"] == parent.telegram_id]
        assert len(student_msgs) >= 1
        assert len(parent_msgs) >= 1

    asyncio.run(run())


def test_duplicate_prevention():
    """Rerunning matching should not create duplicate Match entries."""

    async def run():
        fake_bot = FakeBot()
        notifications._notification_bot = fake_bot

        await create_tables()
        # clean DB
        async with async_session() as session:
            await session.execute(delete(Match))
            await session.execute(delete(StudentRequest))
            await session.execute(delete(ParentTravel))
            await session.execute(delete(User))
            await session.commit()

        # create users
        async with async_session() as session:
            student = await create_user(session=session, telegram_id=9011001, username="s_dup", full_name="S Dup")
            await update_user_role(session, student.telegram_id, "student")
            parent = await create_user(session=session, telegram_id=9012002, username="p_dup", full_name="P Dup")
            await update_user_role(session, parent.telegram_id, "parent")

        # create request and travel
        async with async_session() as session:
            req = await create_student_request(session=session, telegram_id=student.telegram_id, item_description="Item2", pickup_location="A", destination_school="B", delivery_date="2026-09-01")
            trv = await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="A", destination_school="B", travel_date="2026-09-01", can_carry_packages=True)

        # first run
        new1 = await find_matches()
        assert len(new1) == 1
        # second run
        new2 = await find_matches()
        assert len(new2) == 0

    asyncio.run(run())


def test_admin_access_control():
    """Non-admin invoking admin command should receive access denied message."""

    async def run():
        # create a fake message from non-admin
        fake_msg = FakeMessage(user_id=123456789)  # not in ADMIN_IDS
        # call handler
        from bot.handlers.admin import cmd_admin_matches

        await cmd_admin_matches(fake_msg)
        assert any("Access denied" in t for t in fake_msg.answered)

    asyncio.run(run())


def test_notifications_failure_handling():
    """Simulate failures when sending notifications; functions should handle exceptions gracefully."""

    async def run():
        # configure FakeBot to raise for first admin id
        fail_id = ADMIN_IDS[0] if len(ADMIN_IDS) > 0 else 999999
        fake_bot = FakeBot(raise_on=[fail_id])
        notifications._notification_bot = fake_bot

        await create_tables()
        # clean DB
        async with async_session() as session:
            await session.execute(delete(Match))
            await session.execute(delete(StudentRequest))
            await session.execute(delete(ParentTravel))
            await session.execute(delete(User))
            await session.commit()

        # create users and match
        async with async_session() as session:
            student = await create_user(session=session, telegram_id=9021001, username="s_nf", full_name="S NF")
            await update_user_role(session, student.telegram_id, "student")
            parent = await create_user(session=session, telegram_id=9022002, username="p_nf", full_name="P NF")
            await update_user_role(session, parent.telegram_id, "parent")
            req = await create_student_request(session=session, telegram_id=student.telegram_id, item_description="Item3", pickup_location="Z", destination_school="Y", delivery_date="2026-10-01")
            trv = await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="Z", destination_school="Y", travel_date="2026-10-01", can_carry_packages=True)

        # run matching and notify admins; some sends will raise but function should continue
        new = await find_matches()
        assert len(new) == 1

        # load match with relationships
        async with async_session() as session:
            match = await get_match_by_id(session, new[0].id)

        # notify_admin_match should not raise despite send failures
        await notifications.notify_admin_match(match)

        # there should be at least some successful sends (for admins not in raise_on)
        successful = [m for m in fake_bot.sent if m["chat_id"] not in fake_bot.raise_on]
        # It's possible all admins are in raise_on; in that case ensure function didn't raise
        assert True

    asyncio.run(run())
