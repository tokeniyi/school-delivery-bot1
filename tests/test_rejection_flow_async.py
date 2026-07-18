import pytest
from database.db import async_session
from database.crud import create_user, update_user_role, create_student_request, create_parent_travel, reject_match, get_match_by_id, create_match
from services.matching import find_matches
import services.notifications as notifications


@pytest.mark.asyncio
async def test_rejection_flow(fake_bot):
    async with async_session() as session:
        student = await create_user(session=session, telegram_id=9001001, username="s_reject", full_name="S Reject")
        await update_user_role(session, student.telegram_id, "student")
        parent = await create_user(session=session, telegram_id=9002002, username="p_reject", full_name="P Reject")
        await update_user_role(session, parent.telegram_id, "parent")

    async with async_session() as session:
        req = await create_student_request(session=session, telegram_id=student.telegram_id, item_description="Item", pickup_location="X", destination_school="Y", delivery_date="2026-08-01")
        trv = await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="X", destination_school="Y", travel_date="2026-08-01", can_carry_packages=True)

    candidates = await find_matches()
    assert len(candidates) == 1

    req_id, trv_id = candidates[0]
    async with async_session() as session:
        new_match = await create_match(session, req_id, trv_id)
    async with async_session() as session:
        match = await get_match_by_id(session, new_match.id)
        rejected = await reject_match(session, match.id)

    assert rejected.status == 'rejected'
    assert rejected.student_request.status == 'pending'
    assert rejected.parent_travel.status == 'available'

    await notifications.notify_student_rejected(rejected.student_request.user.telegram_id)
    await notifications.notify_parent_rejected(rejected.parent_travel.user.telegram_id)

    student_msgs = [m for m in fake_bot.sent if m['chat_id'] == student.telegram_id]
    parent_msgs = [m for m in fake_bot.sent if m['chat_id'] == parent.telegram_id]
    assert len(student_msgs) >= 1
    assert len(parent_msgs) >= 1


@pytest.mark.asyncio
async def test_parent_cannot_carry_packages_status():
    async with async_session() as session:
        parent = await create_user(session=session, telegram_id=9003003, username="p_nocarry", full_name="P No Carry")
        await update_user_role(session, parent.telegram_id, "parent")
        trv = await create_parent_travel(session=session, telegram_id=parent.telegram_id, origin_location="X", destination_school="Y", travel_date="2026-08-01", can_carry_packages=False)
        assert trv.status == "unavailable"


@pytest.mark.asyncio
async def test_rejected_notification_resubmitted_travel(fake_bot):
    # 1. Create a match and reject it
    async with async_session() as session:
        student = await create_user(session=session, telegram_id=9004004, username="s_resub", full_name="S Resub")
        await update_user_role(session, student.telegram_id, "student")
        parent1 = await create_user(session=session, telegram_id=9005005, username="p_resub1", full_name="P Resub1")
        await update_user_role(session, parent1.telegram_id, "parent")
        parent2 = await create_user(session=session, telegram_id=9006006, username="p_resub2", full_name="P Resub2")
        await update_user_role(session, parent2.telegram_id, "parent")

    async with async_session() as session:
        req = await create_student_request(session=session, telegram_id=student.telegram_id, item_description="ResubItem", pickup_location="A", destination_school="B", delivery_date="2026-08-02")
        trv1 = await create_parent_travel(session=session, telegram_id=parent1.telegram_id, origin_location="A", destination_school="B", travel_date="2026-08-02", can_carry_packages=True)

    candidates = await find_matches()
    assert len(candidates) >= 1
    
    # Match req & trv1
    async with async_session() as session:
        match1 = await create_match(session, req.id, trv1.id)
        await reject_match(session, match1.id)

    # Now parent2 registers similar travel parameters
    async with async_session() as session:
        trv2 = await create_parent_travel(session=session, telegram_id=parent2.telegram_id, origin_location="A", destination_school="B", travel_date="2026-08-02", can_carry_packages=True)

    # Trigger matches again
    candidates2 = await find_matches()
    match_pairs = [c for c in candidates2 if c[0] == req.id and c[1] == trv2.id]
    assert len(match_pairs) == 1

    async with async_session() as session:
        match2 = await create_match(session, req.id, trv2.id)
        loaded = await get_match_by_id(session, match2.id)
        
    notifications._notification_bot = fake_bot
    await notifications.notify_admin_match(loaded)

    assert len(fake_bot.sent) >= 1
    notice_sent = False
    for msg in fake_bot.sent:
        if "Notice:" in msg['text'] and "previously rejected" in msg['text']:
            notice_sent = True
    assert notice_sent

