import asyncio
from datetime import date, timedelta

from database.db import async_session
from database.crud import (
    create_tables, create_user, update_user_role,
    create_student_request, create_parent_travel,
    get_pending_matches
)
from services.matching import find_matches


async def main():
    # Ensure tables exist
    await create_tables()

    travel_date = (date.today() + timedelta(days=1)).isoformat()

    # Create test users
    async with async_session() as session:
        student = await create_user(session, telegram_id=11111004, username="match_student", full_name="Match Student")
        await update_user_role(session, student.telegram_id, "student")

        parent = await create_user(session, telegram_id=11111005, username="match_parent", full_name="Match Parent")
        await update_user_role(session, parent.telegram_id, "parent")

    # Create a student request
    async with async_session() as session:
        req = await create_student_request(
            session=session,
            telegram_id=11111004,
            item_description="Books",
            pickup_location="Abuja",
            destination_school="HighSchoolA",
            delivery_date=travel_date,
        )

    # Create a parent travel
    async with async_session() as session:
        trv = await create_parent_travel(
            session=session,
            telegram_id=11111005,
            origin_location="Abuja",  # case-insensitive test
            destination_school="HighSchoolA",
            travel_date=travel_date,
            can_carry_packages=True,
        )

    # Count matches before
    async with async_session() as session:
        before_matches = await get_pending_matches(session)
        before_count = len(before_matches)

    # Run matching (pure check)
    candidates = await find_matches()

    if not candidates:
        # Debug output: check which condition failed for the single pair we created
        pickup_match = req.pickup_location.strip().lower() == trv.origin_location.strip().lower()
        school_match = req.destination_school.strip().lower() == trv.destination_school.strip().lower()
        date_match   = req.delivery_date.strip() == trv.travel_date.strip()

        print("FAILED")
        if not pickup_match:
            print("  ❌ Pickup location mismatch")
            print(f"    Student pickup={req.pickup_location}, Parent origin={trv.origin_location}")
        if not school_match:
            print("  ❌ Destination school mismatch")
            print(f"    Student school={req.destination_school}, Parent school={trv.destination_school}")
        if not date_match:
            print("  ❌ Date mismatch")
            print(f"    Student date={req.delivery_date}, Parent date={trv.travel_date}")
        if not trv.can_carry_packages:
            print("  ❌ Parent cannot carry packages")
        return

    # Persist and report created matches
    created = []
    async with async_session() as session:
        from database.crud import create_match
        for req_id, trv_id in candidates:
            new_m = await create_match(session, req_id, trv_id)
            if new_m:
                created.append(new_m)

    if created:
        print(f"SUCCESSFUL: {len(created)} match(es) created")
        for m in created:
            print(f"  Match id={m.id} request={m.student_request_id} travel={m.parent_travel_id} status={m.status}")
    else:
        print("FAILED: No match persisted (possible duplicates)")


if __name__ == '__main__':
    asyncio.run(main())
