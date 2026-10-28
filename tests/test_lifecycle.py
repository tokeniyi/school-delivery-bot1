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


async def test_approval_closes_both_competitors_with_reason():
    from database.models import MatchEvent, AuditLog
    ids = await candidates()
    async with async_session() as s:
        await approve_match(s, ids[4], 123456789)
    async with async_session() as s:
        for match_id in ids[5:]:
            m = await s.get(Match, match_id)
            assert m.status == 'closed'
            assert m.closure_reason == f'allocated_by_match:{ids[4]}'
            events = (await s.scalars(select(MatchEvent).where(MatchEvent.match_id == match_id)
                                      .order_by(MatchEvent.id))).all()
            assert [(e.from_status, e.to_status) for e in events] == [(None, 'pending_review'), ('pending_review', 'closed')]
            assert events[-1].reason == m.closure_reason
            assert await reject_match(s, match_id, 123456789) is None
        actions = (await s.scalars(select(AuditLog.action))).all()
        assert sorted(actions) == ['approve', 'auto_close', 'auto_close']
        assert (await s.get(StudentRequest, ids[0])).status == 'matched'
        assert (await s.get(ParentTravel, ids[2])).status == 'matched'


async def test_review_failure_rolls_back_all_state(monkeypatch):
    from database.models import MatchEvent, AuditLog
    ids = await candidates()
    async with async_session() as s:
        async def fail_commit():
            await s.flush()
            raise RuntimeError('simulated transaction failure')
        monkeypatch.setattr(s, 'commit', fail_commit)
        with pytest.raises(RuntimeError, match='simulated transaction'):
            await approve_match(s, ids[4], 123456789)
    async with async_session() as s:
        assert (await s.get(StudentRequest, ids[0])).status == 'pending'
        assert (await s.get(ParentTravel, ids[2])).status == 'available'
        assert set((await s.scalars(select(Match.status))).all()) == {'pending_review'}
        assert not (await s.scalars(select(AuditLog))).all()
        assert set((await s.scalars(select(MatchEvent.to_status))).all()) == {'pending_review'}


async def test_reconsideration_is_explicit_authorized_and_preserves_every_review(fake_bot):
    from database.crud import reconsider_match
    from database.models import MatchEvent, AuditLog
    from services.matching import find_matches
    from services.matching_service import MatchingService
    ids = await candidates()
    async with async_session() as s:
        await reject_match(s, ids[4], 123456789)
    assert (ids[0], ids[2]) not in await find_matches()
    async with async_session() as s:
        assert await create_match(s, ids[0], ids[2]) is None
    with pytest.raises(PermissionError):
        await MatchingService.reconsider_match(ids[4], 999999)
    async with async_session() as s:
        with pytest.raises(PermissionError):
            await reconsider_match(s, ids[4], 999999)
    for revision in (2, 3):
        match = await MatchingService.reconsider_match(ids[4], 123456789)
        assert match.review_revision == revision
        assert match.status == 'pending_review'
        assert match.reviewed_at is None
        assert await MatchingService.reconsider_match(ids[4], 123456789) is None
        async with async_session() as s:
            # The original inline button must never approve a later review round.
            assert await approve_match(s, ids[4], 123456789, expected_revision=1) is None
            if revision == 2:
                await reject_match(s, ids[4], 123456789, expected_revision=revision)
            else:
                await approve_match(s, ids[4], 123456789, expected_revision=revision)
    async with async_session() as s:
        events = (await s.scalars(select(MatchEvent).where(MatchEvent.match_id == ids[4])
                                  .order_by(MatchEvent.id))).all()
        assert [e.to_status for e in events] == ['pending_review', 'rejected', 'pending_review', 'rejected', 'pending_review', 'approved']
        assert [e.actor_id for e in events[1:]] == [123456789] * 5
        audits = (await s.scalars(select(AuditLog.action).where(AuditLog.entity_id == ids[4])
                                  .order_by(AuditLog.id))).all()
        assert audits == ['reject', 'reconsider', 'reject', 'reconsider', 'approve']
    assert len(fake_bot.sent) == 2  # fresh admin cards, no user success notifications


async def test_reconsideration_refuses_resources_allocated_elsewhere():
    from database.crud import reconsider_match
    ids = await candidates()
    async with async_session() as s:
        await reject_match(s, ids[4], 123456789)
        await approve_match(s, ids[5], 123456789)
    async with async_session() as s:
        assert await reconsider_match(s, ids[4], 123456789) is None
        assert (await s.get(Match, ids[4])).status == 'rejected'


@pytest.mark.parametrize('user_id', [999999, 123456789])
async def test_reconsideration_command_authorization(user_id, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from bot.handlers.admin import cmd_reconsider_match
    from services.matching_service import MatchingService
    spy = AsyncMock(return_value=None)
    monkeypatch.setattr(MatchingService, 'reconsider_match', spy)
    message = SimpleNamespace(from_user=SimpleNamespace(id=user_id),
                              text='/reconsider_match 42', answer=AsyncMock())
    await cmd_reconsider_match(message)
    if user_id == 999999:
        spy.assert_not_awaited()
        assert 'Access denied' in message.answer.call_args.args[0]
    else:
        spy.assert_awaited_once_with(42, 123456789)


async def overlapping_operations(ids, operations):
    """Prove two independent backends are blocked before releasing the owner lock."""
    import asyncio
    from sqlalchemy import text
    from database.models import User
    ready = asyncio.Event()
    pids = []
    async def run(operation):
        async with async_session() as s:
            pids.append(await s.scalar(text('SELECT pg_backend_pid()')))
            if len(pids) == 2:
                ready.set()
            return await operation(s)
    async with async_session() as blocker:
        # Both tested operations touch this owner. Hold its row until both other
        # backends demonstrably overlap in PostgreSQL, not just in Python gather.
        owner = await blocker.scalar(select(StudentRequest.user_id).where(StudentRequest.id == ids[0]))
        await blocker.execute(select(User.id).where(User.id == owner).with_for_update())
        tasks = [asyncio.create_task(run(operation)) for operation in operations]
        try:
            await asyncio.wait_for(ready.wait(), 5)
            assert len(set(pids)) == 2
            for _ in range(100):
                async with async_session() as observer:
                    waiting = await observer.scalar(text(
                        "SELECT count(*) FROM pg_stat_activity WHERE pid = ANY(:pids) "
                        "AND wait_event_type = 'Lock'"), {'pids': pids})
                if waiting == 2:
                    break
                await asyncio.sleep(.02)
            else:
                raise AssertionError('Both transactions did not overlap while waiting on PostgreSQL locks')
            await blocker.rollback()
            return await asyncio.wait_for(asyncio.gather(*tasks), 10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize('competitor', [5, 6], ids=['shared-request', 'shared-trip'])
async def test_simultaneous_approvals_have_exactly_one_winner(competitor):
    from database.models import AuditLog
    ids = await candidates()
    # For shared trip use its parent's owner as the common test barrier resource.
    if competitor == 6:
        # The helper locks the owner of ids[0]; make it the same parent by passing
        # a request with that owner only for the barrier, not for actual allocation.
        async with async_session() as s:
            barrier_req = await create_student_request(s, 700002, 'barrier', 'X', 'Y', '2099-01-02')
        barrier_ids = (barrier_req.id, *ids[1:])
    else:
        barrier_ids = ids
    result = await overlapping_operations(barrier_ids, [
        lambda s: approve_match(s, ids[4], 123456789),
        lambda s: approve_match(s, ids[competitor], 123456789),
    ])
    assert sum(m is not None for m in result) == 1
    async with async_session() as s:
        rows = (await s.scalars(select(Match).where(Match.status == 'approved'))).all()
        assert len(rows) == 1
        assert len((await s.scalars(select(AuditLog).where(AuditLog.action == 'approve'))).all()) == 1
        loser = await s.get(Match, ids[competitor] if rows[0].id == ids[4] else ids[4])
        assert loser.status == 'closed'


async def test_simultaneous_approve_reject_is_one_review():
    from database.models import AuditLog, MatchEvent
    ids = await candidates()
    result = await overlapping_operations(ids, [
        lambda s: approve_match(s, ids[4], 123456789),
        lambda s: reject_match(s, ids[4], 123456789),
    ])
    assert sum(m is not None for m in result) == 1
    async with async_session() as s:
        match = await s.get(Match, ids[4])
        audits = (await s.scalars(select(AuditLog).where(AuditLog.entity_id == ids[4]))).all()
        assert len(audits) == 1
        req = await s.get(StudentRequest, ids[0])
        travel = await s.get(ParentTravel, ids[2])
        assert (req.status, travel.status) == (('matched', 'matched') if match.status == 'approved' else ('pending', 'available'))
        events = (await s.scalars(select(MatchEvent).where(MatchEvent.match_id == ids[4]))).all()
        assert len(events) == 2


async def test_simultaneous_resubmissions_do_not_overwrite_approved_history():
    ids = await candidates()
    async with async_session() as s:
        await approve_match(s, ids[4], 123456789)
    result = await overlapping_operations(ids, [
        lambda s: create_student_request(s, 700000, 'New A', 'Z', 'School', '2099-02-03'),
        lambda s: create_student_request(s, 700000, 'New B', 'Z', 'School', '2099-02-03'),
    ])
    assert result[0].id == result[1].id != ids[0]
    async with async_session() as s:
        assert (await s.get(StudentRequest, ids[0])).item_description == 'Original'
        assert len((await s.scalars(select(StudentRequest).where(StudentRequest.user_id == (
            select(StudentRequest.user_id).where(StudentRequest.id == ids[0]).scalar_subquery()
        )))).all()) == 2


@pytest.mark.parametrize('competitor', [5, 6])
async def test_database_constraints_refuse_conflicting_approval(competitor):
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError
    ids = await candidates()
    async with async_session() as s:
        await approve_match(s, ids[4], 123456789)
    async with async_session() as s:
        with pytest.raises(IntegrityError):
            await s.execute(update(Match).where(Match.id == ids[competitor]).values(status='approved'))
            await s.commit()
        await s.rollback()


@pytest.mark.parametrize('kind', ['request', 'travel'])
async def test_pending_edits_close_candidates_and_preserve_old_details(kind):
    from database.models import MatchEvent
    from services.matching import find_matches
    ids = await candidates()
    async with async_session() as s:
        if kind == 'request':
            replacement = await create_student_request(s, 700000, 'Updated item', 'X', 'Y', '2099-01-02')
            old_id = ids[0]
            affected = ids[4:6]
            assert replacement.id != old_id
            expected_pairs = [(replacement.id, ids[2]), (replacement.id, ids[3])]
        else:
            # Whitespace remains a valid matching change and still needs new review.
            replacement = await create_parent_travel(s, 700002, ' X ', 'Y', '2099-01-02', True)
            old_id = ids[2]
            affected = [ids[4], ids[6]]
            assert replacement.id != old_id
            expected_pairs = [(ids[0], replacement.id), (ids[1], replacement.id)]
    async with async_session() as s:
        old = await s.get(StudentRequest if kind == 'request' else ParentTravel, old_id)
        assert old.status == 'superseded'
        assert (old.item_description if kind == 'request' else old.origin_location) == ('Original' if kind == 'request' else 'X')
        for match_id in affected:
            match = await s.get(Match, match_id)
            assert match.status == 'closed'
            assert match.closure_reason == f'source_edited:{kind}:{old_id}'
            assert await approve_match(s, match_id, 123456789) is None
            events = (await s.scalars(select(MatchEvent).where(MatchEvent.match_id == match_id)
                                      .order_by(MatchEvent.id))).all()
            assert events[-1].to_status == 'closed'
            assert events[-1].reason == f'source_edited:{kind}:{old_id}'
    discovered = await find_matches()
    assert all(pair in discovered for pair in expected_pairs)
    async with async_session() as s:
        new_match = await create_match(s, *expected_pairs[0])
        assert new_match.status == 'pending_review'
        assert new_match.id not in affected


@pytest.mark.parametrize('kind', ['request', 'travel'])
async def test_simultaneous_edit_and_approval_preserve_reviewed_details(kind):
    ids = await candidates()
    if kind == 'request':
        edit = lambda s: create_student_request(s, 700000, 'Edited', 'X', 'Y', '2099-01-02')
        barrier_ids = ids
    else:
        edit = lambda s: create_parent_travel(s, 700002, ' X ', 'Y', '2099-01-02', True)
        async with async_session() as s:
            barrier = await create_student_request(s, 700002, 'barrier', 'X', 'Y', '2099-01-02')
        barrier_ids = (barrier.id, *ids[1:])
    result = await overlapping_operations(barrier_ids, [
        lambda s: approve_match(s, ids[4], 123456789), edit,
    ])
    async with async_session() as s:
        match = await s.get(Match, ids[4])
        req = await s.get(StudentRequest, ids[0])
        travel = await s.get(ParentTravel, ids[2])
        assert req.item_description == 'Original'
        assert travel.origin_location == 'X'
        assert result[1].id != (ids[0] if kind == 'request' else ids[2])
        if match.status == 'approved':
            assert result[0] is not None
            assert (req.status, travel.status) == ('matched', 'matched')
        else:
            assert result[0] is None
            assert match.status == 'closed'
            assert (req if kind == 'request' else travel).status == 'superseded'


async def test_losing_service_review_sends_no_success_notifications(fake_bot):
    from services.matching_service import MatchingService
    ids = await candidates()
    assert await MatchingService.approve_match(ids[4], 123456789)
    assert len(fake_bot.sent) == 2
    assert await MatchingService.approve_match(ids[5], 123456789) is None
    assert await MatchingService.reject_match(ids[6], 123456789) is None
    assert len(fake_bot.sent) == 2


async def test_rejection_never_resets_legacy_shared_resource_state():
    from sqlalchemy import update
    ids = await candidates()
    async with async_session() as s:
        # Simulate stale legacy candidate after external resource status changes.
        await s.execute(update(StudentRequest).where(StudentRequest.id == ids[0]).values(status='matched'))
        await s.execute(update(ParentTravel).where(ParentTravel.id == ids[2]).values(status='unavailable', can_carry_packages=False))
        await s.commit()
        assert await reject_match(s, ids[4], 123456789)
    async with async_session() as s:
        assert (await s.get(StudentRequest, ids[0])).status == 'matched'
        assert (await s.get(ParentTravel, ids[2])).status == 'unavailable'
