import asyncio
import asyncpg

async def check_db():
    # Try connecting without specifying database first
    try:
        conn = await asyncpg.connect(
            'postgresql://postgres:postgres@localhost:5432/postgres',
            timeout=10
        )
        print("Connected to postgres DB")
        
        # List all databases
        dbs = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false")
        print("Databases:")
        for db in dbs:
            print(f"  - {db['datname']}")
        
        # Check if schoolrelay exists
        db_names = [r['datname'] for r in dbs]
        if 'schoolrelay' in db_names:
            print("\n✓ schoolrelay database EXISTS")
        else:
            print("\n✗ schoolrelay database DOES NOT EXIST")
            print("  Available databases:", db_names)
        
        await conn.close()
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

asyncio.run(check_db())
