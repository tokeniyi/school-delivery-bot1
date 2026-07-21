# seed_demo_data.py
import asyncio
from datetime import date, timedelta
from database.db import async_session
from database.crud import (
    create_user,
    update_user_role,
    create_student_request,
    create_parent_travel,
    create_match
)

async def seed_data():
    async with async_session() as session:
        # --- Create demo users ---
        student = await create_user(
            session=session,
            telegram_id=8063787998,
            username="student_demo",
            full_name="Demo Student"
        )
        await update_user_role(session, student.telegram_id, "student")

        parent = await create_user(
            session=session,
            telegram_id=6693073272,
            username="parent_demo",
            full_name="Demo Parent"
        )
        await update_user_role(session, parent.telegram_id, "parent")

        # --- Create student requests ---
        req1 = await create_student_request(
            session=session,
            telegram_id=student.telegram_id,
            item_description="Math Textbook",
            pickup_location="Library",
            destination_school="High School A",
            delivery_date=(date.today() + timedelta(days=3)).isoformat()
        )

        req2 = await create_student_request(
            session=session,
            telegram_id=student.telegram_id,
            item_description="Science Kit",
            pickup_location="Lab",
            destination_school="High School B",
            delivery_date=(date.today() + timedelta(days=5)).isoformat()
        )

        # --- Create parent travels ---
        travel1 = await create_parent_travel(
            session=session,
            telegram_id=parent.telegram_id,
            origin_location="City Center",
            destination_school="High School A",  # matches req1 destination
            travel_date=(date.today() + timedelta(days=3)).isoformat(),
            can_carry_packages=True
        )

        travel2 = await create_parent_travel(
            session=session,
            telegram_id=parent.telegram_id,
            origin_location="Town Square",
            destination_school="High School B",  # matches req2 destination
            travel_date=(date.today() + timedelta(days=10)).isoformat(),  # mismatched date
            can_carry_packages=True
        )

        travel3 = await create_parent_travel(
            session=session,
            telegram_id=parent.telegram_id,
            origin_location="Village Road",
            destination_school="High School C",  # no matching student request
            travel_date=(date.today() + timedelta(days=5)).isoformat(),
            can_carry_packages=True
        )

        # --- Create matches manually for testing ---
        await create_match(session, req1.id, travel1.id)  # Perfect match (same school + date)
        await create_match(session, req2.id, travel2.id)  # Destination matches, date mismatch
        await create_match(session, req1.id, travel2.id)  # Date mismatch, different school

    print("✅ Demo users, requests, travels, and matches seeded.")

if __name__ == "__main__":
    asyncio.run(seed_data())
