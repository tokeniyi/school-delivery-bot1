"""Lifecycle invariants against disposable PostgreSQL; all notifications are fake."""
import pytest
from sqlalchemy import select
from database.db import async_session
from database.models import Match, StudentRequest, ParentTravel
from database.crud import (
    create_user, create_student_request, create_parent_travel, create_match,
    approve_match, reject_match,
)


async def candidates():
    async with async_session() as s:
        for i in range(4):
            await create_user(s, 700000 + i, f'life{i}', f'Lifecycle {i}')
        r1 = await create_student_request(s, 700000, 'Original', 'X', 'Y', '2099-01-02')
        r2 = await create_student_request(s, 700001, 'Other', 'X', 'Y', '2099-01-02')
        t1 = await create_parent_travel(s, 700002, 'X', 'Y', '2099-01-02', True)
        t2 = await create_parent_travel(s, 700003, 'X', 'Y', '2099-01-02', True)
        m1 = await create_match(s, r1.id, t1.id)
        m2 = await create_match(s, r1.id, t2.id)
        m3 = await create_match(s, r2.id, t1.id)
    return r1.id, r2.id, t1.id, t2.id, m1.id, m2.id, m3.id


@pytest.mark.parametrize('competitor', [5, 6], ids=['same-request', 'same-trip'])
async def test_conflicting_approval_is_refused(competitor):
    ids = await candidates()
    async with async_session() as s:
        assert await approve_match(s, ids[4], 123456789)
    async with async_session() as s:
        assert await approve_match(s, ids[competitor], 123456789) is None
    async with async_session() as s:
        approved = (await s.scalars(select(Match).where(Match.status == 'approved'))).all()
        assert [m.id for m in approved] == [ids[4]]


@pytest.mark.parametrize('kind', ['request', 'travel'])
async def test_resubmission_preserves_approved_history(kind):
    ids = await candidates()
    async with async_session() as s:
        await approve_match(s, ids[4], 123456789)
    async with async_session() as s:
        if kind == 'request':
            new = await create_student_request(s, 700000, 'New', 'Z', 'School', '2099-02-03')
            assert new.id != ids[0]
            assert new.status == 'pending'
        else:
            new = await create_parent_travel(s, 700002, 'Z', 'School', '2099-02-03', False)
            assert new.id != ids[2]
            assert new.status == 'unavailable'
    async with async_session() as s:
        req = await s.get(StudentRequest, ids[0])
        travel = await s.get(ParentTravel, ids[2])
        assert (req.item_description, req.pickup_location, req.status) == ('Original', 'X', 'matched')
        assert (travel.origin_location, travel.status, travel.can_carry_packages) == ('X', 'matched', True)
        approved = await s.get(Match, ids[4])
        assert (approved.student_request_id, approved.parent_travel_id) == (ids[0], ids[2])
