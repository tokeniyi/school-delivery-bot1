import pytest
import asyncio
from datetime import datetime, date, timedelta
from sqlalchemy import select, delete
from database.db import async_session
from database.crud import (
    create_user, update_user_role, upsert_student_request, upsert_parent_travel,
    create_match, get_pending_matches, get_match_by_id, approve_match, reject_match
)
from database.models import User, StudentRequest, ParentTravel, Match
from services.matching import find_matches
import services.notifications as notifications
from config import ADMIN_IDS

class FakeBot:
    def __init__(self, raise_on=None):
        self.sent = []
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
        self.answered = []

    async def answer(self, text, **kwargs):
        self.answered.append(text)

class FakeCallback:
    def __init__(self, user_id: int, data: str, message=None):
        class U:
            def __init__(self, id):
                self.id = id
        self.from_user = U(user_id)
        self.data = data
        self.message = message or FakeMessage(user_id)
        self.answered_alerts = []

    async def answer(self, text, show_alert=False):
        self.answered_alerts.append((text, show_alert))

# Clean up helper
async def setup_test_users():
    async with async_session() as session:
        # Create unique users
        student = await create_user(session, 80000001, "student_qa", "QA Student")
        await update_user_role(session, student.telegram_id, "student")
        
        parent = await create_user(session, 80000002, "parent_qa", "QA Parent")
        await update_user_role(session, parent.telegram_id, "parent")
        return student, parent

@pytest.mark.asyncio
async def test_qa_matching_engine():
    student, parent = await setup_test_users()
    travel_date = (date.today() + timedelta(days=10)).isoformat()

    # M-001: Student request without matching parent
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, "Books", "Ojota", "Babcock University", travel_date)
    candidates = await find_matches()
    assert len(candidates) == 0, "M-001 Failed"

    # M-002: Parent trip without student request (school mismatched to create non-matching parent)
    async with async_session() as session:
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Other University", travel_date, True)
    candidates = await find_matches()
    assert len(candidates) == 0, "M-002 Failed"

    # M-003: Perfect match
    async with async_session() as session:
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", travel_date, True)
    candidates = await find_matches()
    assert len(candidates) == 1, "M-003 Failed"
    assert candidates[0] == (req.id, trv.id)

    # M-004: Different pickup location
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, "Books", "Ikeja", "Babcock University", travel_date)
    candidates = await find_matches()
    assert len(candidates) == 0, "M-004 Failed"

    # M-005: Different destination school
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, "Books", "Ojota", "Covenant University", travel_date)
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", travel_date, True)
    candidates = await find_matches()
    assert len(candidates) == 0, "M-005 Failed"

    # M-006: Different travel date
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, "Books", "Ojota", "Babcock University", travel_date)
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", (date.today() + timedelta(days=20)).isoformat(), True)
    candidates = await find_matches()
    assert len(candidates) == 0, "M-006 Failed"

    # M-007: Parent unavailable (can_carry_packages=False)
    async with async_session() as session:
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", travel_date, False)
    candidates = await find_matches()
    assert len(candidates) == 0, "M-007 Failed"

@pytest.mark.asyncio
async def test_qa_duplicate_prevention():
    student, parent = await setup_test_users()
    travel_date = (date.today() + timedelta(days=10)).isoformat()

    # D-001 / D-003: Double runs & duplicate match checks
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, "Books", "Ojota", "Babcock University", travel_date)
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", travel_date, True)

    candidates1 = await find_matches()
    assert len(candidates1) == 1
    
    # Persist the match
    async with async_session() as session:
        await create_match(session, req.id, trv.id)

    # Second run should skip it
    candidates2 = await find_matches()
    assert len(candidates2) == 0, "D-001/D-003 Failed"

@pytest.mark.asyncio
async def test_qa_admin_authorization():
    # A-001: Unauthorized /admin_matches access denied
    from bot.handlers.admin import cmd_admin_matches, callback_approve_match
    
    unauthorized_msg = FakeMessage(user_id=999999)  # Not in ADMIN_IDS
    await cmd_admin_matches(unauthorized_msg)
    assert any("Access denied" in text for text in unauthorized_msg.answered), "A-001 Failed"

    # A-002: Unauthorized callback data access denied
    unauthorized_cb = FakeCallback(user_id=999999, data="approve_match_1")
    await callback_approve_match(unauthorized_cb)
    assert any("Access denied" in pair[0] for pair in unauthorized_cb.answered_alerts), "A-002 Failed"

@pytest.mark.asyncio
async def test_qa_notification_failures():
    # N-005: Notification failure handling
    fail_admin = ADMIN_IDS[0] if len(ADMIN_IDS) > 0 else 999999
    fb = FakeBot(raise_on=[fail_admin])
    notifications._notification_bot = fb

    student, parent = await setup_test_users()
    travel_date = (date.today() + timedelta(days=10)).isoformat()
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, "Books", "Ojota", "Babcock University", travel_date)
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", travel_date, True)
        match = await create_match(session, req.id, trv.id)
        # Load match with relations
        loaded = await get_match_by_id(session, match.id)

    # Calling notify_admin_match should not raise exception despite FakeBot raising RuntimeError
    try:
        await notifications.notify_admin_match(loaded)
    except Exception as e:
        pytest.fail(f"N-005 failed: Exception raised during notifications broadcast: {e}")

@pytest.mark.asyncio
async def test_qa_approval_and_rejection_workflows():
    student, parent = await setup_test_users()
    travel_date = (date.today() + timedelta(days=10)).isoformat()
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, "Books", "Ojota", "Babcock University", travel_date)
        trv = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", travel_date, True)
        match = await create_match(session, req.id, trv.id)

    # P-001 & P-002: Approve valid match and verify statuses + reviewed_at
    async with async_session() as session:
        approved = await approve_match(session, match.id)
        
    assert approved is not None
    assert approved.status == "approved"
    assert approved.reviewed_at is not None
    
    # Reload and check associated entities status
    async with async_session() as session:
        rel_req = (await session.execute(select(StudentRequest).where(StudentRequest.id == req.id))).scalar_one()
        rel_trv = (await session.execute(select(ParentTravel).where(ParentTravel.id == trv.id))).scalar_one()
    assert rel_req.status == "matched"
    assert rel_trv.status == "matched"

    # P-003: Approve twice should be blocked (return None)
    async with async_session() as session:
        approved_second = await approve_match(session, match.id)
    assert approved_second is None, "P-003 Failed"

    # R-001 & R-002: Rejection checks
    async with async_session() as session:
        # Create a new match to test rejection
        req2 = await upsert_student_request(session, student.telegram_id, "Pens", "Ojota", "Babcock University", travel_date)
        # Note: upsert_parent_travel will overwrite parent's previous available travel. Since previous was matched, it creates a new available one.
        trv2 = await upsert_parent_travel(session, parent.telegram_id, "Ojota", "Babcock University", travel_date, True)
        match2 = await create_match(session, req2.id, trv2.id)
        
        # Reject the match
        rejected = await reject_match(session, match2.id)
    
    assert rejected is not None
    assert rejected.status == "rejected"
    assert rejected.reviewed_at is not None
    
    # R-002: Reject twice should return None
    async with async_session() as session:
        rejected_second = await reject_match(session, match2.id)
    assert rejected_second is None, "R-002 Failed"

    # R-003: Approve rejected match should return None
    async with async_session() as session:
        approve_rejected = await approve_match(session, match2.id)
    assert approve_rejected is None, "R-003 Failed"

@pytest.mark.asyncio
async def test_qa_database_integrity_and_sql_injection():
    # SQL Injection attempt stored as plaintext
    student, parent = await setup_test_users()
    travel_date = (date.today() + timedelta(days=10)).isoformat()
    injection_payload = "'; DROP TABLE matches; --"
    
    async with async_session() as session:
        req = await upsert_student_request(session, student.telegram_id, injection_payload, "Ojota", "Babcock University", travel_date)
        
    assert req.item_description == injection_payload
    
    # Query database directly to verify matches table exists and is intact
    async with async_session() as session:
        stmt = select(Match)
        # Should not raise an exception because the table is intact
        await session.execute(stmt)
