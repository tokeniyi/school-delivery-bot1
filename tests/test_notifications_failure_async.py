import pytest
from database.db import async_session
from database.crud import create_user, update_user_role, create_student_request, create_parent_travel, get_match_by_id, create_match
from services.matching import find_matches
import services.notifications as notifications
from config import ADMIN_IDS


@pytest.mark.asyncio
async def test_notifications_failure_handling(fake_bot):
    # configure fake bot to raise for first admin
    fail_id = ADMIN_IDS[0] if len(ADMIN_IDS) > 0 else 999999
    fake_bot.raise_on.add(fail_id)

    async with async_session() as session:
        student = await create_user(session=session, telegram_id=9021001, username="s_nf", full_name="S NF")
        await update_user_role(session, student.telegram_id, "student")
        parent = await create_user(session=session, telegram_id=9022002, username="p_nf", full_name="P NF")
        await update_user_role(session, parent.telegram_id, "parent")

    async with async_session() as session:
        await create_student_request(session=session, telegram_id=student.telegram_id, item_description="Item3", pickup_location="Z", destination_school="Y", delivery_date="2026-10-01")
        await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="Z", destination_school="Y", travel_date="2026-10-01", can_carry_packages=True)

    candidates = await find_matches()
    assert len(candidates) == 1

    req_id, trv_id = candidates[0]
    async with async_session() as session:
        new_match = await create_match(session, req_id, trv_id)
    async with async_session() as session:
        match = await get_match_by_id(session, new_match.id)

    # should not raise
    await notifications.notify_admin_match(match)

    # ensure function continued despite some failures (no exception means pass)
    assert True
