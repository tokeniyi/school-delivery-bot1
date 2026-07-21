"""
Core matching engine test scenarios.

Tests the find_matches() function against all 5 core rules:
  Rule 1 — Location compatibility
  Rule 2 — Date compatibility
  Rule 3 — Parent availability (can_carry_packages)
  Rule 4 — User isolation (no self-match)
  Rule 5 — Strict parameter matching
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
from database.enums import MatchStatus
from services.matching import find_matches
from sqlalchemy import delete


# ===== Helpers =====

async def _clean_db():
    async with async_session() as session:
        await session.execute(delete(Match))
        await session.execute(delete(StudentRequest))
        await session.execute(delete(ParentTravel))
        await session.execute(delete(User))
        await session.commit()


async def _run_find_matches():
    candidates = await find_matches()
    return candidates


async def _persist_matches(candidates):
    """Persist candidate pairs as Match records (mirrors production flow)."""
    async with async_session() as session:
        created = []
        for student_request_id, parent_travel_id in candidates:
            match = Match(
                student_request_id=student_request_id,
                parent_travel_id=parent_travel_id,
                status="pending_review",
            )
            session.add(match)
            created.append(match)
        await session.commit()
        for m in created:
            await session.refresh(m)
        return created


# ===== Test Scenarios =====

class TestScenarioAPerfectMatch:
    """T001 — Perfect Match (PASS)"""

    @pytest.mark.asyncio
    async def test_perfect_match_creates_match(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(
                session=session, telegram_id=1001, username="parent_a", full_name="Parent A"
            )
            from database.enums import Role
            await session.execute(delete(User))
            await session.commit()
            parent = await create_user(
                session=session, telegram_id=1001, username="parent_a", full_name="Parent A"
            )
            from database.crud import update_user_role
            await update_user_role(session, parent.telegram_id, "parent")

            student = await create_user(
                session=session, telegram_id=2001, username="student_a", full_name="Student A"
            )
            await update_user_role(session, student.telegram_id, "student")

            from tests.matchtest.fixtures import seed_perfect_match_scenario
            req, travel = await seed_perfect_match_scenario(session, parent, student)

        candidates = await _run_find_matches()
        assert len(candidates) == 1
        assert candidates[0] == (req.id, travel.id)

        matches = await _persist_matches(candidates)
        assert len(matches) == 1
        assert matches[0].student_request_id == req.id
        assert matches[0].parent_travel_id == travel.id


class TestScenarioBDateMismatch:
    """T002 — Date Mismatch (FAIL)"""

    @pytest.mark.asyncio
    async def test_date_mismatch_prevents_match(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(
                session=session, telegram_id=1002, username="parent_b", full_name="Parent B"
            )
            from database.crud import update_user_role
            await update_user_role(session, parent.telegram_id, "parent")

            student = await create_user(
                session=session, telegram_id=2002, username="student_b", full_name="Student B"
            )
            await update_user_role(session, student.telegram_id, "student")

            from tests.matchtest.fixtures import seed_date_mismatch_scenario
            req, travel = await seed_date_mismatch_scenario(session, parent, student)

        candidates = await _run_find_matches()
        assert len(candidates) == 0


class TestScenarioCLocationMismatch:
    """T003 — Location Mismatch (FAIL)"""

    @pytest.mark.asyncio
    async def test_pickup_mismatch_prevents_match(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(
                session=session, telegram_id=1003, username="parent_c1", full_name="Parent C1"
            )
            from database.crud import update_user_role
            await update_user_role(session, parent.telegram_id, "parent")

            student = await create_user(
                session=session, telegram_id=2003, username="student_c1", full_name="Student C1"
            )
            await update_user_role(session, student.telegram_id, "student")

            from tests.matchtest.fixtures import seed_location_mismatch_scenarios
            reqs, travels = await seed_location_mismatch_scenarios(session, parent, student)

        candidates = await _run_find_matches()
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_destination_mismatch_prevents_match(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(
                session=session, telegram_id=1004, username="parent_c2", full_name="Parent C2"
            )
            from database.crud import update_user_role
            await update_user_role(session, parent.telegram_id, "parent")

            student = await create_user(
                session=session, telegram_id=2004, username="student_c2", full_name="Student C2"
            )
            await update_user_role(session, student.telegram_id, "student")

            from tests.matchtest.fixtures import seed_location_mismatch_scenarios
            reqs, travels = await seed_location_mismatch_scenarios(session, parent, student)

        candidates = await _run_find_matches()
        assert len(candidates) == 0


class TestScenarioDAvailabilityDisabled:
    """T004 — Availability Disabled (FAIL)"""

    @pytest.mark.asyncio
    async def test_unavailable_parent_prevents_match(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(
                session=session, telegram_id=1005, username="parent_d", full_name="Parent D"
            )
            from database.crud import update_user_role
            await update_user_role(session, parent.telegram_id, "parent")

            student = await create_user(
                session=session, telegram_id=2005, username="student_d", full_name="Student D"
            )
            await update_user_role(session, student.telegram_id, "student")

            from tests.matchtest.fixtures import seed_availability_disabled_scenario
            req, travel = await seed_availability_disabled_scenario(session, parent, student)

        candidates = await _run_find_matches()
        assert len(candidates) == 0


class TestScenarioESelfMatchingPrevention:
    """T005 — Self Matching Prevention (FAIL)"""

    @pytest.mark.asyncio
    async def test_self_matching_is_forbidden(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            overlap = await create_user(
                session=session, telegram_id=3000, username="overlap", full_name="David"
            )
            from database.crud import update_user_role
            await update_user_role(session, overlap.telegram_id, "parent")

            from tests.matchtest.fixtures import seed_self_matching_scenario
            req, travel = await seed_self_matching_scenario(session, overlap)

        candidates = await _run_find_matches()
        assert len(candidates) == 0


class TestScenarioFCaseSensitivityAndWhitespace:
    """T006 — Case Sensitivity and Whitespace (PASS — system normalizes)"""

    @pytest.mark.asyncio
    async def test_case_insensitive_match_succeeds(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(
                session=session, telegram_id=1006, username="parent_f", full_name="Parent F"
            )
            from database.crud import update_user_role
            await update_user_role(session, parent.telegram_id, "parent")

            student = await create_user(
                session=session, telegram_id=2006, username="student_f", full_name="Student F"
            )
            await update_user_role(session, student.telegram_id, "student")

            from tests.matchtest.fixtures import seed_case_sensitivity_scenarios
            req, travel = await seed_case_sensitivity_scenarios(session, parent, student)

        candidates = await _run_find_matches()
        assert len(candidates) == 1
        assert candidates[0] == (req.id, travel.id)


class TestScenarioGMultiplePossibleMatches:
    """T007 — Multiple Possible Matches"""

    @pytest.mark.asyncio
    async def test_multiple_matches_all_created(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parents = []
            students = []
            for i in range(3):
                u = await create_user(
                    session=session, telegram_id=100 + i, username=f"parent_m{i}", full_name=f"Parent M{i}"
                )
                await update_user_role(session, u.telegram_id, "parent")
                parents.append(u)

            u = await create_user(
                session=session, telegram_id=200, username="student_m", full_name="Student M"
            )
            await update_user_role(session, u.telegram_id, "student")
            students.append(u)

            from tests.matchtest.fixtures import seed_multiple_matches_scenario
            req, travels = await seed_multiple_matches_scenario(session, students, parents)

        candidates = await _run_find_matches()
        assert len(candidates) == 2
        expected = {(req.id, travels[0].id), (req.id, travels[1].id)}
        assert set(candidates) == expected


class TestScenarioHMissingData:
    """T008 — Missing Data (empty strings — NOT NULL DB constraint prevents actual NULL insertion)"""

    @pytest.mark.asyncio
    async def test_empty_pickup_location_prevents_match(self):
        await _clean_db()
        await create_tables()

        async with async_session() as session:
            parent = await create_user(
                session=session, telegram_id=1007, username="parent_h", full_name="Parent H"
            )
            from database.crud import update_user_role
            await update_user_role(session, parent.telegram_id, "parent")

            student = await create_user(
                session=session, telegram_id=2007, username="student_h", full_name="Student H"
            )
            await update_user_role(session, student.telegram_id, "student")

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
