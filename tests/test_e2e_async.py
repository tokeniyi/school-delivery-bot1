import pytest
import asyncio
from database.db import async_session
from database.crud import (
    create_user, update_user_role,
    create_student_request, create_parent_travel, approve_match, get_match_by_id, create_match
)
from services.matching import find_matches
import services.notifications as notifications


@pytest.mark.asyncio
async def test_full_flow(fake_bot):
    # create users
    async with async_session() as session:
        student = await create_user(session=session, telegram_id=9991001, username="student_test", full_name="Student Test")
        await update_user_role(session, student.telegram_id, "student")
        parent = await create_user(session=session, telegram_id=9992002, username="parent_test", full_name="Parent Test")
        await update_user_role(session, parent.telegram_id, "parent")

    # create request and travel
    async with async_session() as session:
        req = await create_student_request(session=session, telegram_id=student.telegram_id, item_description="Test Package", pickup_location="CityA", destination_school="HighSchoolX", delivery_date="2026-07-01")
        trv = await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="CityA", destination_school="HighSchoolX", travel_date="2026-07-01", can_carry_packages=True)

    # run matching (check-only)
    candidates = await find_matches()
    assert len(candidates) == 1

    # persist created match and load with relationships
    req_id, trv_id = candidates[0]
    async with async_session() as session:
        new_match = await create_match(session, req_id, trv_id)
    async with async_session() as session:
        match = await get_match_by_id(session, new_match.id)
    await notifications.notify_admin_match(match)

    # simulate admin approval
    async with async_session() as session:
        approved = await approve_match(session, match.id)

    assert approved is not None and approved.status == "approved"

    # send notifications
    await notifications.notify_student_approved(approved.student_request.user.telegram_id)
    await notifications.notify_parent_approved(approved.parent_travel.user.telegram_id)

    # verify notifications
    student_msgs = [m for m in fake_bot.sent if m['chat_id'] == student.telegram_id]
    parent_msgs = [m for m in fake_bot.sent if m['chat_id'] == parent.telegram_id]
    assert len(student_msgs) >= 1
    assert len(parent_msgs) >= 1

    # verify db statuses
    async with async_session() as session:
        loaded = await get_match_by_id(session, match.id)
        assert loaded.status == 'approved'
        assert loaded.student_request.status == 'matched'
        assert loaded.parent_travel.status == 'matched'
