import sys
import os
import asyncio

# Add the workspace directory to the path so python can import database module
sys.path.append(r"c:\Users\user\Documents\htdocs\Repo\telegram-bot\bot1\school-delivery-bot")

from database.db import async_session
from database.crud import create_user, get_user_by_telegram_id, update_user_role, create_student_request

async def test():
    print("Beginning CRUD operations test assertions...")
    async with async_session() as session:
        # 1. Create a test user
        user = await create_user(session, 123456789, "test_user", "Test Full Name")
        print(f"  - Created/updated user: {user}")
        assert user.telegram_id == 123456789
        
        # 2. Get user by telegram_id
        fetched_user = await get_user_by_telegram_id(session, 123456789)
        print(f"  - Fetched user by telegram_id: {fetched_user}")
        assert fetched_user is not None
        assert fetched_user.username == "test_user"
        
        # 3. Update user role
        updated_user = await update_user_role(session, 123456789, "student")
        print(f"  - Updated user role: {updated_user}")
        assert updated_user.role == "student"
        
        # 4. Create a student delivery request linked to the user
        req = await create_student_request(
            session=session,
            telegram_id=123456789,
            item_description="Textbooks",
            pickup_location="Lekki",
            destination_school="Babcock University",
            delivery_date="2026-06-15"
        )
        print(f"  - Created student request: {req}")
        assert req.item_description == "Textbooks"
        assert req.pickup_location == "Lekki"
        assert req.destination_school == "Babcock University"
        assert req.delivery_date == "2026-06-15"
        assert req.status == "pending"
        
        print("Success: All CRUD operational assertions passed!")

if __name__ == "__main__":
    asyncio.run(test())

