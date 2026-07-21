import asyncio
import sys
import os

# Force reload of config to see what's happening
sys.path.insert(0, os.getcwd())

# First, show what dotenv finds
from dotenv import load_dotenv
load_dotenv(".env")
env_local = os.path.join(os.getcwd(), ".env.local")
load_dotenv(env_local, override=True)

print("=== Raw os.getenv values ===")
print(f"ENVIRONMENT = {os.getenv('ENVIRONMENT')!r}")
print(f"DATABASE_URL = {os.getenv('DATABASE_URL')!r}")
print(f"REDIS_URL = {os.getenv('REDIS_URL')!r}")
print(f"BOT_TOKEN = {os.getenv('BOT_TOKEN')!r}")
print()

# Now import config module
import config
print("=== config.py resolved values ===")
print(f"ENVIRONMENT = {config.ENVIRONMENT!r}")
print(f"DATABASE_URL = {config.DATABASE_URL!r}")
print(f"REDIS_URL = {config.REDIS_URL!r}")
print()

# Try a direct asyncpg connection test
async def test_connection():
    import asyncpg
    url = config.DATABASE_URL
    print(f"=== Attempting asyncpg connection to: {url} ===")
    try:
        conn = await asyncpg.connect(url, timeout=10)
        print("SUCCESS: Connected!")
        result = await conn.fetchval("SELECT version()")
        print(f"PostgreSQL version: {result}")
        await conn.close()
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

asyncio.run(test_connection())
