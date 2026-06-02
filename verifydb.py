import sys
import os
import asyncio

# Add the workspace directory to the path so python can import database module
sys.path.append(r"c:\Users\user\Documents\htdocs\Repo\telegram-bot\bot1\school-delivery-bot")

from database.db import async_session
from database.crud import create_user, update_user_role, create_parent_travel, get_parent_travel, update_parent_travel_status
from database.crud import create_tables

async def test():
    print("Beginning Parent CRUD operations test assertions...")
    
    # 1. Initialize Tables (ensuring migrations trigger)
    await create_tables()
    print("  - Database tables verified and initialized.")

    async with async_session() as session:
        # 2. Create a test parent user
        user = await create_user(session, 987654321, "parent_user", "Parent Full Name")
        print(f"  - Created/updated user: {user}")
        assert user.telegram_id == 987654321
        
        # 3. Update user role to parent
        updated_user = await update_user_role(session, 987654321, "parent")
        print(f"  - Updated user role to parent: {updated_user}")
        assert updated_user.role == "parent"
        
        # 4. Create a parent travel availability schedule linked to the user
        travel = await create_parent_travel(
            session=session,
            telegram_id=987654321,
            origin_location="Ikeja",
            destination_school="Covenant University",
            travel_date="2026-06-20",
            can_carry_packages=True
        )
        print(f"  - Created travel availability: {travel}")
        assert travel.origin_location == "Ikeja"
        assert travel.destination_school == "Covenant University"
        assert travel.travel_date == "2026-06-20"
        assert travel.can_carry_packages is True
        assert travel.status == "available"
        
        # 5. Fetch travel records by telegram ID
        records = await get_parent_travel(session, 987654321)
        print(f"  - Fetched parent travels: {records}")
        assert len(records) > 0
        assert any(r.origin_location == "Ikeja" for r in records)
        
        # 6. Update travel status
        updated_travel = await update_parent_travel_status(session, travel.id, "matched")
        print(f"  - Updated travel status: {updated_travel}")
        assert updated_travel.status == "matched"
        
        print("Success: All Parent CRUD operational assertions passed!")

if __name__ == "__main__":
    asyncio.run(test())

