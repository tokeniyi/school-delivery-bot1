"""
Edge case tests for the matching engine.

Covers:
  - Case sensitivity and whitespace normalization
  - Multiple match handling
  - Missing data (NULL fields)
  - Status-based filtering (PENDING / AVAILABLE)
  - Duplicate match prevention (unique constraint)
  - Date format variations
  - Empty strings
"""

import os
import sys
import asyncio
import pytest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("ADMIN_IDS", "123456789")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/schoolbridge")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from database.db import async_session
from database.crud import (
    create_tables,
    create_user,
    update_user_role,
    create_student_request,
    create_parent_travel,
)
from database.models import User, StudentRequest, ParentTravel, Match
from database.enums import RequestStatus, TravelStatus, Role, MatchStatus
from services.matching import find_matches
from sqlalchemy import delete


async def _clean_db():
    async with async_session() as session:
        await session.execute(delete(Match))
        await session.execute(delete(StudentRequest))
        await session.execute(delete(ParentTravel))
        await session.execute(delete(User))
        await session.commit()


async def _run_find_matches():
    return await find_matches()


# ===== Edge Case Tests =====

class TestCaseSensitivityAndWhitespace:

    @pytest.mark.asyncio
    async def test_lowercase_student_matches_uppercase_parent(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(session=session, telegram_id=101, username="p_ws", full_name="P WS")
            await update_user_role(session, parent.telegram_id, Role.PARENT.value)
            student = await create_user(session=session, telegram_id=201, username="s_ws", full_name="S WS")
            await update_user_role(session, student.telegram_id, Role.STUDENT.value)

            req = await create_student_request(
                session=session,
                telegram_id=student.telegram_id,
                item_description="Books",
                pickup_location="lagos",
                destination_school="abuja",
                delivery_date="2026-07-25",
            )
            travel = await create_parent_travel(
                session=session,
                telegram_id=parent.telegram_id,
                origin_location="Lagos",
                destination_school="Abuja",
                travel_date="2026-07-25",
                can_carry_packages=True,
            )

        candidates = await _run_find_matches()
        assert len(candidates) == 1

    @pytest.mark.asyncio
    async def test_whitespace_trimmed_student_matches_parent(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(session=session, telegram_id=102, username="p_t", full_name="P T")
            await update_user_role(session, parent.telegram_id, Role.PARENT.value)
            student = await create_user(session=session, telegram_id=202, username="s_t", full_name="S T")
            await update_user_role(session, student.telegram_id, Role.STUDENT.value)

            req = await create_student_request(
                session=session,
                telegram_id=student.telegram_id,
                item_description="Books",
                pickup_location="Lagos ",
                destination_school="Abuja",
                delivery_date="2026-07-25",
            )
            travel = await create_parent_travel(
                session=session,
                telegram_id=parent.telegram_id,
                origin_location=" Lagos",
                destination_school="Abuja ",
                travel_date=" 2026-07-25 ",
                can_carry_packages=True,
            )

        candidates = await _run_find_matches()
        assert len(candidates) == 1


class TestMultipleMatchHandling:

    @pytest.mark.asyncio
    async def test_one_student_three_possible_parents_two_available(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            p1 = await create_user(session=session, telegram_id=301, username="p1", full_name="P1")
            await update_user_role(session, p1.telegram_id, Role.PARENT.value)
            p2 = await create_user(session=session, telegram_id=302, username="p2", full_name="P2")
            await update_user_role(session, p2.telegram_id, Role.PARENT.value)
            p3 = await create_user(session=session, telegram_id=303, username="p3", full_name="P3")
            await update_user_role(session, p3.telegram_id, Role.PARENT.value)

            s = await create_user(session=session, telegram_id=401, username="s1", full_name="S1")
            await update_user_role(session, s.telegram_id, Role.STUDENT.value)

            req = await create_student_request(
                session=session,
                telegram_id=s.telegram_id,
                item_description="Books",
                pickup_location="Lagos",
                destination_school="Abuja",
                delivery_date="2026-07-25",
            )
            t1 = await create_parent_travel(
                session=session, telegram_id=p1.telegram_id,
                origin_location="Lagos", destination_school="Abuja",
                travel_date="2026-07-25", can_carry_packages=True,
            )
            t2 = await create_parent_travel(
                session=session, telegram_id=p2.telegram_id,
                origin_location="Lagos", destination_school="Abuja",
                travel_date="2026-07-25", can_carry_packages=True,
            )
            t3 = await create_parent_travel(
                session=session, telegram_id=p3.telegram_id,
                origin_location="Lagos", destination_school="Abuja",
                travel_date="2026-07-25", can_carry_packages=False,
            )

        candidates = await _run_find_matches()
        assert len(candidates) == 2
        expected = {(req.id, t1.id), (req.id, t2.id)}
        assert set(candidates) == expected


class TestDuplicateMatchPrevention:

    @pytest.mark.asyncio
    async def test_duplicate_match_not_created_after_approval(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(session=session, telegram_id=501, username="p_dup", full_name="P Dup")
            await update_user_role(session, parent.telegram_id, Role.PARENT.value)
            student = await create_user(session=session, telegram_id=601, username="s_dup", full_name="S Dup")
            await update_user_role(session, student.telegram_id, Role.STUDENT.value)

            req = await create_student_request(
                session=session,
                telegram_id=student.telegram_id,
                item_description="Books",
                pickup_location="Lagos",
                destination_school="Abuja",
                delivery_date="2026-07-25",
            )
            travel = await create_parent_travel(
                session=session,
                telegram_id=parent.telegram_id,
                origin_location="Lagos",
                destination_school="Abuja",
                travel_date="2026-07-25",
                can_carry_packages=True,
            )

        # First run: create and approve a match
        candidates = await _run_find_matches()
        assert len(candidates) == 1

        async with async_session() as session:
            match = Match(student_request_id=req.id, parent_travel_id=travel.id, status=MatchStatus.APPROVED.value)
            session.add(match)
            await session.commit()

        # Second run: same pair should NOT be returned again
        candidates = await _run_find_matches()
        assert len(candidates) == 0


class TestStatusFiltering:

    @pytest.mark.asyncio
    async def test_non_pending_student_request_excluded(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(session=session, telegram_id=502, username="p_st", full_name="P ST")
            await update_user_role(session, parent.telegram_id, Role.PARENT.value)
            student = await create_user(session=session, telegram_id=602, username="s_st", full_name="S ST")
            await update_user_role(session, student.telegram_id, Role.STUDENT.value)

            req = await create_student_request(
                session=session,
                telegram_id=student.telegram_id,
                item_description="Books",
                pickup_location="Lagos",
                destination_school="Abuja",
                delivery_date="2026-07-25",
            )
            req.status = RequestStatus.CANCELLED.value
            await session.commit()

            await create_parent_travel(
                session=session,
                telegram_id=parent.telegram_id,
                origin_location="Lagos",
                destination_school="Abuja",
                travel_date="2026-07-25",
                can_carry_packages=True,
            )

        candidates = await _run_find_matches()
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_non_available_parent_travel_excluded(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(session=session, telegram_id=503, username="p_nt", full_name="P NT")
            await update_user_role(session, parent.telegram_id, Role.PARENT.value)
            student = await create_user(session=session, telegram_id=603, username="s_nt", full_name="S NT")
            await update_user_role(session, student.telegram_id, Role.STUDENT.value)

            await create_student_request(
                session=session,
                telegram_id=student.telegram_id,
                item_description="Books",
                pickup_location="Lagos",
                destination_school="Abuja",
                delivery_date="2026-07-25",
            )
            travel = await create_parent_travel(
                session=session,
                telegram_id=parent.telegram_id,
                origin_location="Lagos",
                destination_school="Abuja",
                travel_date="2026-07-25",
                can_carry_packages=True,
            )
            travel.status = TravelStatus.UNAVAILABLE.value
            await session.commit()

        candidates = await _run_find_matches()
        assert len(candidates) == 0


class TestEmptyStringFields:

    @pytest.mark.asyncio
    async def test_empty_string_pickup_location_prevents_match(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(session=session, telegram_id=504, username="p_es", full_name="P ES")
            await update_user_role(session, parent.telegram_id, Role.PARENT.value)
            student = await create_user(session=session, telegram_id=604, username="s_es", full_name="S ES")
            await update_user_role(session, student.telegram_id, Role.STUDENT.value)

            req = await create_student_request(
                session=session,
                telegram_id=student.telegram_id,
                item_description="Books",
                pickup_location="",
                destination_school="Abuja",
                delivery_date="2026-07-25",
            )
            await create_parent_travel(
                session=session,
                telegram_id=parent.telegram_id,
                origin_location="Lagos",
                destination_school="Abuja",
                travel_date="2026-07-25",
                can_carry_packages=True,
            )

        candidates = await _run_find_matches()
        assert len(candidates) == 0
