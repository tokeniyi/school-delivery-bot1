import pytest
from database.db import async_session
from database.crud import create_user, update_user_role, create_student_request, create_parent_travel, create_match
from services.matching import find_matches


@pytest.mark.asyncio
async def test_duplicate_prevention(fake_bot):
    async with async_session() as session:
        student = await create_user(session=session, telegram_id=9011001, username="s_dup", full_name="S Dup")
        await update_user_role(session, student.telegram_id, "student")
        parent = await create_user(session=session, telegram_id=9012002, username="p_dup", full_name="P Dup")
        await update_user_role(session, parent.telegram_id, "parent")

    async with async_session() as session:
        req = await create_student_request(session=session, telegram_id=student.telegram_id, item_description="Item2", pickup_location="A", destination_school="B", delivery_date="2026-09-01")
        trv = await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="A", destination_school="B", travel_date="2026-09-01", can_carry_packages=True)

    candidates1 = await find_matches()
    assert len(candidates1) == 1
    req_id, trv_id = candidates1[0]
    async with async_session() as session:
        await create_match(session, req_id, trv_id)

    candidates2 = await find_matches()
    assert len(candidates2) == 0
