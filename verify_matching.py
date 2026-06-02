"""
Phase 4 Verification Script
Tests: Match model schema, CRUD operations, matching service logic, duplicate prevention.
"""
import asyncio
import sys
import os

from database.db import async_session, engine
from database.models import Base, User, StudentRequest, ParentTravel, Match
from database.crud import (
    create_tables, create_match, match_exists, get_pending_matches,
    get_match_by_id, approve_match, reject_match
)
from sqlalchemy import select, inspect


async def verify_schema():
    """Verify the matches table exists with the correct columns."""
    print("=" * 60)
    print("1. SCHEMA VERIFICATION")
    print("=" * 60)
    
    async with engine.connect() as conn:
        def check_tables(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()
        
        tables = await conn.run_sync(check_tables)
        
    expected_tables = ["users", "student_requests", "parent_travels", "matches"]
    for t in expected_tables:
        status = "✅" if t in tables else "❌"
        print(f"  {status} Table '{t}' exists: {t in tables}")
    
    # Verify matches table columns
    async with engine.connect() as conn:
        def check_columns(sync_conn):
            inspector = inspect(sync_conn)
            return [col["name"] for col in inspector.get_columns("matches")]
        
        columns = await conn.run_sync(check_columns)
    
    expected_cols = ["id", "student_request_id", "parent_travel_id", "status", "created_at", "reviewed_at"]
    for c in expected_cols:
        status = "✅" if c in columns else "❌"
        print(f"  {status} Column 'matches.{c}' exists: {c in columns}")
    
    print()
    return all(t in tables for t in expected_tables) and all(c in columns for c in expected_cols)


async def verify_matching_logic():
    """Test the matching CRUD and service logic."""
    print("=" * 60)
    print("2. MATCHING CRUD VERIFICATION")
    print("=" * 60)
    
    async with async_session() as session:
        # Create test users
        student_user = User(telegram_id=999001, username="test_student", full_name="Test Student", role="student")
        parent_user = User(telegram_id=999002, username="test_parent", full_name="Test Parent", role="parent")
        session.add_all([student_user, parent_user])
        await session.commit()
        await session.refresh(student_user)
        await session.refresh(parent_user)
        print(f"  ✅ Created test student (id={student_user.id}) and parent (id={parent_user.id})")

        # Create a student request
        request = StudentRequest(
            user_id=student_user.id,
            item_description="Test Textbooks",
            pickup_location="Lagos",
            destination_school="University of Lagos",
            delivery_date="2026-07-01",
            status="pending"
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)
        print(f"  ✅ Created student request (id={request.id})")

        # Create a matching parent travel
        travel = ParentTravel(
            user_id=parent_user.id,
            origin_location="Lagos",
            destination_school="University of Lagos",
            travel_date="2026-07-01",
            can_carry_packages=True,
            status="available"
        )
        session.add(travel)
        await session.commit()
        await session.refresh(travel)
        print(f"  ✅ Created parent travel (id={travel.id})")

        # Test match_exists (should be False)
        exists_before = await match_exists(session, request.id, travel.id)
        status = "✅" if not exists_before else "❌"
        print(f"  {status} match_exists before creation: {exists_before} (expected: False)")

        # Test create_match
        match = await create_match(session, request.id, travel.id)
        status = "✅" if match and match.status == "pending_review" else "❌"
        print(f"  {status} create_match: Match#{match.id}, status='{match.status}'")

        # Test match_exists (should be True now)
        exists_after = await match_exists(session, request.id, travel.id)
        status = "✅" if exists_after else "❌"
        print(f"  {status} match_exists after creation: {exists_after} (expected: True)")

        # Test get_pending_matches
        pending = await get_pending_matches(session)
        status = "✅" if len(pending) >= 1 else "❌"
        print(f"  {status} get_pending_matches: {len(pending)} pending match(es)")

        # Test get_match_by_id with eager loading
        loaded_match = await get_match_by_id(session, match.id)
        has_relations = (
            loaded_match is not None
            and loaded_match.student_request is not None
            and loaded_match.parent_travel is not None
            and loaded_match.student_request.user is not None
            and loaded_match.parent_travel.user is not None
        )
        status = "✅" if has_relations else "❌"
        print(f"  {status} get_match_by_id with eager loading: relationships loaded={has_relations}")

        # Test approve_match
        approved = await approve_match(session, match.id)
        approve_ok = (
            approved is not None
            and approved.status == "approved"
            and approved.reviewed_at is not None
            and approved.student_request.status == "matched"
            and approved.parent_travel.status == "matched"
        )
        status = "✅" if approve_ok else "❌"
        print(f"  {status} approve_match: match.status='{approved.status}', "
              f"request.status='{approved.student_request.status}', "
              f"travel.status='{approved.parent_travel.status}'")

        # Create another match to test rejection
        request2 = StudentRequest(
            user_id=student_user.id,
            item_description="Test Laptop",
            pickup_location="Abuja",
            destination_school="University of Abuja",
            delivery_date="2026-07-15",
            status="pending"
        )
        travel2 = ParentTravel(
            user_id=parent_user.id,
            origin_location="Abuja",
            destination_school="University of Abuja",
            travel_date="2026-07-15",
            can_carry_packages=True,
            status="available"
        )
        session.add_all([request2, travel2])
        await session.commit()
        await session.refresh(request2)
        await session.refresh(travel2)

        match2 = await create_match(session, request2.id, travel2.id)
        rejected = await reject_match(session, match2.id)
        reject_ok = (
            rejected is not None
            and rejected.status == "rejected"
            and rejected.reviewed_at is not None
            # Request and travel should remain unchanged on rejection
            and rejected.student_request.status == "pending"
            and rejected.parent_travel.status == "available"
        )
        status = "✅" if reject_ok else "❌"
        print(f"  {status} reject_match: match.status='{rejected.status}', "
              f"request.status='{rejected.student_request.status}', "
              f"travel.status='{rejected.parent_travel.status}'")

        # Cleanup test data
        await session.delete(match)
        await session.delete(match2)
        await session.delete(request)
        await session.delete(request2)
        await session.delete(travel)
        await session.delete(travel2)
        await session.delete(student_user)
        await session.delete(parent_user)
        await session.commit()
        print(f"  ✅ Cleaned up test data")

    print()
    return approve_ok and reject_ok


async def verify_matching_service():
    """Test the find_matches() service function."""
    print("=" * 60)
    print("3. MATCHING SERVICE VERIFICATION")
    print("=" * 60)

    from services.matching import find_matches

    async with async_session() as session:
        # Setup: create users, matching request, and travel
        student = User(telegram_id=888001, username="svc_student", full_name="SVC Student", role="student")
        parent = User(telegram_id=888002, username="svc_parent", full_name="SVC Parent", role="parent")
        session.add_all([student, parent])
        await session.commit()
        await session.refresh(student)
        await session.refresh(parent)

        # Create matching pair
        req = StudentRequest(
            user_id=student.id, item_description="Books",
            pickup_location="Ibadan", destination_school="UI",
            delivery_date="2026-08-01", status="pending"
        )
        trv = ParentTravel(
            user_id=parent.id, origin_location="ibadan",  # lowercase to test case-insensitive
            destination_school="ui",  # lowercase to test case-insensitive
            travel_date="2026-08-01", can_carry_packages=True, status="available"
        )
        # Non-matching travel (different date)
        trv_no = ParentTravel(
            user_id=parent.id, origin_location="Ibadan",
            destination_school="UI",
            travel_date="2026-09-01", can_carry_packages=True, status="available"
        )
        session.add_all([req, trv, trv_no])
        await session.commit()
        await session.refresh(req)
        await session.refresh(trv)
        await session.refresh(trv_no)

    # Run matching
    new_matches = await find_matches()
    status = "✅" if len(new_matches) == 1 else "❌"
    print(f"  {status} find_matches found {len(new_matches)} match(es) (expected: 1)")

    # Run again - should find 0 new matches (duplicate prevention)
    new_matches_2 = await find_matches()
    status = "✅" if len(new_matches_2) == 0 else "❌"
    print(f"  {status} find_matches re-run found {len(new_matches_2)} new match(es) (expected: 0, duplicate prevention)")

    # Cleanup
    async with async_session() as session:
        # Delete matches first
        stmt = select(Match).where(Match.student_request_id == req.id)
        result = await session.execute(stmt)
        for m in result.scalars().all():
            await session.delete(m)
        await session.delete(req)
        await session.delete(trv)
        await session.delete(trv_no)
        await session.delete(student)
        await session.delete(parent)
        await session.commit()
        print(f"  ✅ Cleaned up test data")

    print()
    return len(new_matches) == 1 and len(new_matches_2) == 0


async def main():
    print("\n🔍 Phase 4 Verification: Matching & Admin Review System\n")

    await create_tables()

    schema_ok = await verify_schema()
    crud_ok = await verify_matching_logic()
    service_ok = await verify_matching_service()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    results = {
        "Schema Verification": schema_ok,
        "Matching CRUD": crud_ok,
        "Matching Service": service_ok,
    }
    all_pass = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("🎉 All Phase 4 verifications passed!")
    else:
        print("⚠️  Some verifications failed. Please review.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
