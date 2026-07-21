"""
Database seed data for matching engine tests.

Provides factory helpers to insert users, student requests, parent travels,
and matches into the database for deterministic test scenarios.
"""

from database.crud import (
    create_user,
    update_user_role,
    create_student_request,
    create_parent_travel,
    approve_match,
)
from database.models import User, StudentRequest, ParentTravel, Match
from database.enums import RequestStatus, TravelStatus, Role
from datetime import datetime, timezone


# ===== Database IDs =====
PARENT1_ID = 1
PARENT2_ID = 2
PARENT3_ID = 3
PARENT4_ID = 4
STUDENT1_ID = 5
STUDENT2_ID = 6
STUDENT3_ID = 7
STUDENT4_ID = 8
OVERLAP_USER_ID = 10


# ===== Locations and Dates =====
LAGOS = "Lagos"
ABUJA = "Abuja"
PORT_HARCOURT = "Port Harcourt"
DATE_MATCH = "2026-07-25"
DATE_MISMATCH = "2026-07-26"


async def seed_base_users(session):
    """Create 4 parent users and 4 student users."""
    parents = []
    students = []
    for i in range(4):
        u = await create_user(
            session=session,
            telegram_id=100 + i,
            username=f"parent{i+1}",
            full_name=f"Parent {i+1}",
        )
        await update_user_role(session, u.telegram_id, Role.PARENT.value)
        parents.append(u)

    for i in range(4):
        u = await create_user(
            session=session,
            telegram_id=200 + i,
            username=f"student{i+1}",
            full_name=f"Student {i+1}",
        )
        await update_user_role(session, u.telegram_id, Role.STUDENT.value)
        students.append(u)

    return parents, students


async def seed_overlap_user(session):
    """Create one user who creates both a parent travel and a student request."""
    u = await create_user(
        session=session,
        telegram_id=300,
        username="overlap_user",
        full_name="David",
    )
    await update_user_role(session, u.telegram_id, Role.PARENT.value)
    return u


async def seed_perfect_match_scenario(session, parent, student):
    """Scenario A: Perfect match (location + date + availability)."""
    travel = await create_parent_travel(
        session=session,
        telegram_id=parent.telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    req = await create_student_request(
        session=session,
        telegram_id=student.telegram_id,
        item_description="Books",
        pickup_location=LAGOS,
        destination_school=ABUJA,
        delivery_date=DATE_MATCH,
    )
    return req, travel


async def seed_date_mismatch_scenario(session, parent, student):
    """Scenario B: Date mismatch."""
    travel = await create_parent_travel(
        session=session,
        telegram_id=parent.telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MISMATCH,
        can_carry_packages=True,
    )
    req = await create_student_request(
        session=session,
        telegram_id=student.telegram_id,
        item_description="Books",
        pickup_location=LAGOS,
        destination_school=ABUJA,
        delivery_date=DATE_MATCH,
    )
    return req, travel


async def seed_location_mismatch_scenarios(session, parent, student):
    """Scenario C: Location mismatch (pickup mismatch and destination mismatch)."""
    travels = []
    reqs = []

    # C1: Pickup mismatch
    req1 = await create_student_request(
        session=session,
        telegram_id=student.telegram_id,
        item_description="Books",
        pickup_location=LAGOS,
        destination_school=ABUJA,
        delivery_date=DATE_MATCH,
    )
    travel1 = await create_parent_travel(
        session=session,
        telegram_id=parent.telegram_id,
        origin_location=ABUJA,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    reqs.append(req1)
    travels.append(travel1)

    # C2: Destination mismatch
    req2 = await create_student_request(
        session=session,
        telegram_id=student.telegram_id,
        item_description="Clothes",
        pickup_location=LAGOS,
        destination_school=PORT_HARCOURT,
        delivery_date=DATE_MATCH,
    )
    travel2 = await create_parent_travel(
        session=session,
        telegram_id=parent.telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    reqs.append(req2)
    travels.append(travel2)

    return reqs, travels


async def seed_availability_disabled_scenario(session, parent, student):
    """Scenario D: Parent unavailable."""
    travel = await create_parent_travel(
        session=session,
        telegram_id=parent.telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=False,
    )
    req = await create_student_request(
        session=session,
        telegram_id=student.telegram_id,
        item_description="Books",
        pickup_location=LAGOS,
        destination_school=ABUJA,
        delivery_date=DATE_MATCH,
    )
    return req, travel


async def seed_self_matching_scenario(session, overlap_user):
    """Scenario E: Self matching prevention."""
    travel = await create_parent_travel(
        session=session,
        telegram_id=overlap_user.telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    req = await create_student_request(
        session=session,
        telegram_id=overlap_user.telegram_id,
        item_description="Books",
        pickup_location=LAGOS,
        destination_school=ABUJA,
        delivery_date=DATE_MATCH,
    )
    return req, travel


async def seed_case_sensitivity_scenarios(session, parent, student):
    """Scenario F: Case sensitivity and whitespace handling."""
    req = await create_student_request(
        session=session,
        telegram_id=student.telegram_id,
        item_description="Books",
        pickup_location="lagos",
        destination_school="abuja",
        delivery_date=DATE_MATCH,
    )
    travel = await create_parent_travel(
        session=session,
        telegram_id=parent.telegram_id,
        origin_location="Lagos ",
        destination_school="Abuja",
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    return req, travel


async def seed_multiple_matches_scenario(session, students, parents):
    """Scenario G: Multiple possible matches for one student request."""
    req = await create_student_request(
        session=session,
        telegram_id=students[0].telegram_id,
        item_description="Books",
        pickup_location=LAGOS,
        destination_school=ABUJA,
        delivery_date=DATE_MATCH,
    )
    travel1 = await create_parent_travel(
        session=session,
        telegram_id=parents[0].telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    travel2 = await create_parent_travel(
        session=session,
        telegram_id=parents[1].telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    travel3 = await create_parent_travel(
        session=session,
        telegram_id=parents[2].telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=False,
    )
    return req, [travel1, travel2, travel3]


async def seed_missing_data_scenarios(session, parent, student):
    """Scenario H: Missing required data (null values)."""
    req = await create_student_request(
        session=session,
        telegram_id=student.telegram_id,
        item_description="Books",
        pickup_location=None,
        destination_school=ABUJA,
        delivery_date=DATE_MATCH,
    )
    travel = await create_parent_travel(
        session=session,
        telegram_id=parent.telegram_id,
        origin_location=LAGOS,
        destination_school=ABUJA,
        travel_date=DATE_MATCH,
        can_carry_packages=True,
    )
    return req, travel
