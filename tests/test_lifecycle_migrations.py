"""Migration safety checks use separate disposable databases, never production."""
import asyncio
from contextlib import asynccontextmanager
import os
import sys
from uuid import uuid4
from urllib.parse import urlsplit

import asyncpg
import pytest
from config import DATABASE_URL


@asynccontextmanager
async def scratch_database():
    dsn = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    parts = urlsplit(dsn)
    assert parts.hostname in ('127.0.0.1', 'localhost'), 'Migration tests require disposable loopback services'
    name = 'lifecycle_migration_' + uuid4().hex[:12]
    admin = await asyncpg.connect(dsn)
    await admin.execute(f'CREATE DATABASE "{name}"')
    scratch = parts._replace(path='/' + name).geturl()
    try:
        yield scratch
    finally:
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()


async def alembic(dsn, *args, succeeds=True):
    env = dict(os.environ, DATABASE_URL=dsn.replace('postgresql://', 'postgresql+asyncpg://'))
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'alembic', *args, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await asyncio.wait_for(process.communicate(), 30)
    output = output.decode()
    assert (process.returncode == 0) == succeeds, output
    return output


async def legacy_rows(conn, shared='request'):
    await conn.execute("INSERT INTO users(id, telegram_id, role) VALUES (1, 100, 'student')")
    await conn.execute("""INSERT INTO student_requests
        (id,user_id,item_description,pickup_location,destination_school,delivery_date,status)
        VALUES (1,1,'original','X','Y','2099-01-02','matched'),
               (2,1,'other','X','Y','2099-01-02','matched')""")
    await conn.execute("""INSERT INTO parent_travels
        (id,user_id,origin_location,destination_school,travel_date,can_carry_packages,status)
        VALUES (1,1,'X','Y','2099-01-02',true,'matched'),
               (2,1,'X','Y','2099-01-02',true,'matched')""")
    await conn.execute("""INSERT INTO matches
        (id,student_request_id,parent_travel_id,status,created_at)
        VALUES (1,1,1,'approved',now())""")
    if shared:
        req, trip = (1, 2) if shared == 'request' else (2, 1)
        await conn.execute("""INSERT INTO matches
            (id,student_request_id,parent_travel_id,status,created_at)
            VALUES (2,$1,$2,'approved',now())""", req, trip)


@pytest.mark.parametrize('shared', ['request', 'trip'])
async def test_migration_refuses_conflicts_without_reconciliation(shared):
    async with scratch_database() as dsn:
        await alembic(dsn, 'upgrade', '5196523efe8d')
        conn = await asyncpg.connect(dsn)
        try:
            await legacy_rows(conn, shared)
            before = await conn.fetch('SELECT * FROM matches ORDER BY id')
            output = await alembic(dsn, 'upgrade', 'head', succeeds=False)
            assert 'requires separately authorized reconciliation' in output
            assert await conn.fetch('SELECT * FROM matches ORDER BY id') == before
            assert await conn.fetchval('SELECT version_num FROM alembic_version') == '5196523efe8d'
            assert not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='match_events')")
        finally:
            await conn.close()


async def test_migration_roundtrip_and_legacy_rejection_history():
    async with scratch_database() as dsn:
        await alembic(dsn, 'upgrade', '5196523efe8d')
        conn = await asyncpg.connect(dsn)
        try:
            await legacy_rows(conn, shared=None)
            await conn.execute("UPDATE matches SET status='rejected', reviewed_at=now()")
            await conn.execute("INSERT INTO audit_logs(admin_id,action,entity_type,entity_id,created_at) VALUES (123456789,'reject','match',1,now())")
            await alembic(dsn, 'upgrade', 'head')
            await alembic(dsn, 'check')
            event = await conn.fetchrow('SELECT * FROM match_events')
            assert event['to_status'] == 'rejected'
            assert event['reason'] == 'legacy_state_at_migration'
            assert event['actor_id'] is None  # no invented history
            assert await conn.fetchval('SELECT count(*) FROM audit_logs') == 1
            await alembic(dsn, 'downgrade', '5196523efe8d')
            await alembic(dsn, 'upgrade', 'head')
            await alembic(dsn, 'check')
        finally:
            await conn.close()
    async with scratch_database() as dsn:
        await alembic(dsn, 'upgrade', 'head')
        await alembic(dsn, 'downgrade', 'base')
        await alembic(dsn, 'upgrade', 'head')
        await alembic(dsn, 'check')


async def test_downgrade_refuses_to_erase_new_review_history():
    async with scratch_database() as dsn:
        await alembic(dsn, 'upgrade', 'head')
        conn = await asyncpg.connect(dsn)
        try:
            await legacy_rows(conn, shared=None)
            await conn.execute("""INSERT INTO match_events
                (match_id,from_status,to_status,actor_id,reason,created_at)
                VALUES(1,'pending_review','approved',123456789,'admin_approval',now())""")
            output = await alembic(dsn, 'downgrade', '5196523efe8d', succeeds=False)
            assert 'would discard lifecycle history' in output
            assert await conn.fetchval('SELECT count(*) FROM match_events') == 1
            assert await conn.fetchval('SELECT version_num FROM alembic_version') == 'a28c10'
        finally:
            await conn.close()
