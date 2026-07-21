import asyncio
import sys
import os

sys.path.insert(0, os.getcwd())
import config

async def test_sqlalchemy():
    from sqlalchemy import text
    from database.db import engine
    
    url = config.DATABASE_URL
    print(f"DATABASE_URL = {url!r}")
    print(f"ENGINE = {engine}")
    print()
    
    print("=== Testing SQLAlchemy engine connection ===")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            row = result.fetchone()
            print(f"SUCCESS: {row[0]}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_sqlalchemy())
