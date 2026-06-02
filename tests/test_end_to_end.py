import asyncio
from typing import List

from database.db import async_session
from database.crud import (
    create_tables, create_user, update_user_role,
    create_student_request, create_parent_travel,
    get_match_by_id, approve_match
)
from services.matching import find_matches
import services.notifications as notifications
from config import ADMIN_IDS


class FakeBot:
    def __init__(self):
        self.sent: List[dict] = []

    async def send_message(self, chat_id, text, **kwargs):
        # Record minimal details for assertions
        self.sent.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})


def test_full_flow():
    """End-to-end flow (synchronous wrapper using asyncio.run).

    Steps:
    - create tables
    - create student and parent users
    - student creates request
    - parent creates travel
    - run matching -> new match created
    - notify admins
    - admin approves (DB update)
    - send approval notifications to student and parent
    - verify DB statuses and captured notifications
    """

    async def run_flow():
        # Use a FakeBot to capture outgoing messages
        fake_bot = FakeBot()
        notifications._notification_bot = fake_bot

        # Ensure tables exist
        await create_tables()

        # Create users and set roles
        async with async_session() as session:
            student = await create_user(session=session, telegram_id=9991001, username="student_test", full_name="Student Test")
            await update_user_role(session, student.telegram_id, "student")

            parent = await create_user(session=session, telegram_id=9992002, username="parent_test", full_name="Parent Test")
            await update_user_role(session, parent.telegram_id, "parent")

        # Create student request
        async with async_session() as session:
            req = await create_student_request(
                session=session,
                telegram_id=student.telegram_id,
                item_description="Test Package",
                pickup_location="CityA",
                destination_school="HighSchoolX",
                delivery_date="2026-07-01",
            )

        # Create parent travel that matches the request
        async with async_session() as session:
            trv = await create_parent_travel(
                session=session,
                telegram_id=parent.telegram_id,
                origin_location="CityA",
                destination_school="HighSchoolX",
                travel_date="2026-07-01",
                can_carry_packages=True,
            )

        # Run matching service
        new_matches = await find_matches()
        assert len(new_matches) == 1, f"Expected 1 new match, got {len(new_matches)}"
        match = new_matches[0]

        # Notify admins about the match (mirrors handler behavior)
        await notifications.notify_admin_match(match)

        # Check admin notifications were sent
        admin_msgs = [m for m in fake_bot.sent if m["chat_id"] in ADMIN_IDS]
        assert len(admin_msgs) == len(ADMIN_IDS), "Admins did not receive expected notifications"

        # Simulate admin approval: update DB (handler normally does this)
        async with async_session() as session:
            approved = await approve_match(session, match.id)

        assert approved is not None and approved.status == "approved"

        # Send approval notifications
        await notifications.notify_student_approved(approved.student_request.user.telegram_id)
        await notifications.notify_parent_approved(approved.parent_travel.user.telegram_id)

        # Verify student and parent notifications were sent
        student_msgs = [m for m in fake_bot.sent if m["chat_id"] == student.telegram_id]
        parent_msgs = [m for m in fake_bot.sent if m["chat_id"] == parent.telegram_id]

        assert len(student_msgs) >= 1, "Student did not receive approval notification"
        assert len(parent_msgs) >= 1, "Parent did not receive approval notification"

        # Verify database statuses reflect approval
        async with async_session() as session:
            loaded = await get_match_by_id(session, match.id)
            assert loaded is not None
            assert loaded.status == "approved", f"Match status is {loaded.status}, expected 'approved'"
            assert loaded.student_request.status == "matched", f"Request status is {loaded.student_request.status}"
            assert loaded.parent_travel.status == "matched", f"Travel status is {loaded.parent_travel.status}"

    asyncio.run(run_flow())
