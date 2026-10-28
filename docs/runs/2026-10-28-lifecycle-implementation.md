# Lifecycle implementation — 2026-10-28

## Verified provenance and authorization

Repository: `tokeniyi/school-delivery-bot1`. Active branch:
`fix/lifecycle-2026-10-28`. Base: fetched latest main at
`f368a5be55d2e3815c6cd8be5f195d1bd14f981f`, the merge of
[PR #6](https://github.com/tokeniyi/school-delivery-bot1/pull/6). GitHub confirms
PR #6 merged October 27 at 16:24:34 Africa/Lagos. Both the lifecycle plan and
continuity documents are present on that main commit; no prerequisite blocked work.

Original checkout remained clean on `work` at `cd0b905`; both previous worktrees
were preserved. Created `/workspace/work/school-delivery-lifecycle` from fetched
main. No reset, overwrite, force push, merge, production access or deployment.
Read AGENTS, existing instructions, implementation plan, progress, architecture,
relevant persistence/services/handlers/tests/migrations and the prior run reports.
Earlier reports are historical; their open-PR and unresolved-policy statements do
not override the user's current instructions.

User confirmed one request per trip; approval closes incompatible candidates with
reason/history, distinct from rejection; approved sources survive new submissions;
rejected pairs require explicit authorized reconsideration retaining reviews.
User also answered the pending-edit question during this run: **allow edits, close
candidates and require fresh review**. The [current contract](../lifecycle-decisions-2026-10-28.md)
records those decisions, transitions and remaining boundaries. No unanswered policy
blocks normal lifecycle behavior.

## Bounded phases and evidence

| Phase | Gate and result |
| --- | --- |
| P0 preparation | Main/PR #6/documents verified; unchanged baseline **44 passed, 1 skipped**, 12.14s |
| P1 red regressions | **4 failed**, 0.57s, unchanged application: shared-request approval, shared-trip approval, approved request mutation, approved travel mutation |
| P2 schema/atomic lifecycle | Original four regressions green; **6 passed**, 1.05s with automatic-closure reasons/history and injected-transaction rollback |
| P3 reconsideration | **10 passed**, 1.44s including configured-admin guards, repeat rejection/reconsideration history, ineligible/duplicate reopen and stale review revision |
| P4 contention and migrations | **20 lifecycle tests passed**, 3.39s including pending edits and true contention; **4 migration tests passed**, 8.57s |
| P5 final validation | **70 passed, 1 skipped**, 24.60s; head/current/check, dependencies, compilation, whitespace and changed-document links passed; publication recorded below |

Phase P1 evidence is committed at
`a6bc22b` (`test: demonstrate allocation conflicts and approved-history mutation`).
The application at that commit remains the verified main baseline. To repeat the
red gate, use that commit with a disposable database at revision `5196523efe8d`,
then `python -m pytest -q tests/test_lifecycle.py`; never downgrade shared data.
Implementation/schema/tests/contract are committed at
`c586c21` (`fix: enforce atomic exclusive delivery lifecycle and preserve review history`).
Subsequent documentation commits update this handoff/publication only.

An intermediate pending-edit test run had **18 passed/2 failed**: assertions read an
ORM object expired by an intentional no-op rollback, raising MissingGreenlet. The
assertion was corrected to use the expected recorded reason; the phase rerun passed
20 tests. This was a test construction error, not an unresolved application failure.
Full-suite checkpoints were 60 passed/1 skipped before the edit extension and
68 passed/1 skipped before the last two edge cases. No failed gate is marked complete.

## Implemented behavior

- Owner-row locks in ascending user ID order serialize submission, candidate
  creation, review and explicit reconsideration. Candidate rows are locked in
  ascending ID order, including crossed competitors. Eligibility is reloaded after
  locking. Allocation, resource status, automatic closure, history and audits commit
  atomically. This serializes per participating user rather than globally.
- Partial unique approved-request and approved-trip indexes enforce exclusivity
  even for direct SQL writers. Pair uniqueness remains.
- Approval closes incompatible pending rows with `allocated_by_match:<winner-id>`;
  automatic `closed` is distinct from admin `rejected`. MatchEvent retains the
  transition/reason; admin-triggered closure also has `auto_close` audit entries.
- Rejection records the review without resetting resource status, so it cannot
  release another allocation or reactivate an unavailable trip.
- Upserts select only documented editable states and exclude approved associations.
  New submissions after approval create new rows; approved fields/IDs stay intact.
  Ambiguous multiple legacy drafts produce an explicit error, not arbitrary selection.
- An edit to a source with candidate history preserves its old details as a
  `superseded` row and inserts a replacement. Pending old candidates close with a
  `source_edited:<kind>:<id>` event/reason. Matching must create fresh candidates
  against the replacement; old source/candidate details remain readable.
- Automatic discovery excludes all previously considered pairs. Configured admins
  may explicitly use `/reconsider_match ID`, guarded in handler/service/CRUD. It
  appends an event/audit, advances review_revision and preserves prior rejection
  events. Old inline buttons identify round 1 and cannot act on later rounds.
- Success notifications occur after committed successful transitions. Losing/stale
  service reviews send no success notification; all test notifications use fakes.
  Existing retry behavior remains, without claiming durable delivery.

## Disposable validation and reproduction

Created PostgreSQL 16 and Redis 7 containers named `lifecycle-pg-20261028` and
`lifecycle-redis-20261028`, bound to loopback 55432/56379 with no existing volumes.
Neither `.env` nor `.env.local` was present in the new worktree. Every database/test
command used explicit dummy/local configuration via an ignored `work/validate.sh`:

```bash
export BOT_TOKEN=123456:TESTTOKEN
export ENVIRONMENT=development
export DATABASE_URL=postgresql+asyncpg://postgres:lifecycle_test@127.0.0.1:55432/lifecycle
export REDIS_URL=redis://127.0.0.1:56379/0
export ADMIN_IDS=123456789
export PATH=/workspace/schoolbridge-venv/bin:$PATH
mkdir -p work
alembic upgrade head
python -m pytest -q -rs --log-file=work/final-tests.log
alembic heads
alembic current
alembic check
python -m compileall -q bot database services migrations tests config.py main.py
uv pip check --python /workspace/schoolbridge-venv/bin/python
git diff --check
```

Local-service/network shell commands required approved execution. Interpreter:
Python 3.11.17. Dependency check: 40 packages compatible. Migration single head and
current: **a28c10**, no new upgrade operations. Redis PING: True (health only).
Final logs contain only two expected simulated notification failures; no loop,
connection-close or MissingGreenlet errors. Legacy module skip remains
`tests/test_additional_flows.py:3`, “moved to split tests.”

Contention tests use independent PostgreSQL backend PIDs. A third transaction holds
an owner row until **both** operations are observed in pg_stat_activity waiting on
locks. Releasing it proves overlapping database work, beyond a Python gather or
sequential loop. Covered shared-request approvals, shared-trip approvals,
approve/reject, concurrent post-approval submissions and both source edit/approval
races. Separate tests assert direct-SQL exclusivity, losing-service notification
suppression, legacy resource-state preservation and atomic failure rollback.

Migration tests create/drop uniquely named databases on the disposable instance:

- Fresh full upgrade/downgrade-to-base/re-upgrade/check.
- Legacy rejected state and existing audit retention through upgrade/check and
  downgrade-to-previous/re-upgrade/check; actors/transitions are not invented.
- Both kinds of conflicting legacy approvals block upgrade and leave rows/schema
  revision unchanged. No automatic winner selection or reconciliation.
- New lifecycle history blocks downgrade that would erase it.

The migration acquires a writer-blocking table lock while checking conflicts and
adding unique indexes; production rollout/lock duration was not exercised. Full
round trips run only on disposable data. Both test containers and anonymous data
volumes were removed after validation; existing schoolbridge containers untouched.
No production URL/data, Telegram polling, webhook deletion, live messages or bot
container startup was used.

## Remaining work and decisions

No failing check or normal-path policy blocker remains. Legacy multiple editable
rows require explicit selection/reconciliation policy; they fail clearly. Any
existing production conflicting approvals require separately authorized human
resolution before this migration can complete; no production inspection occurred.

Cancellation/completion, deletion/retention, freezing shared user display names,
legacy stored-date cleanup, Redis outages/FSM integration, middleware, production
pool/performance/container runtime, Telegram limits and durable delivery remain
outside this task. These tests do not claim production readiness or load safety.
The current locking protocol serializes per user and assumes PostgreSQL's normal
READ COMMITTED application isolation; external writers must respect the contract,
with database indexes providing allocation defense in depth.

## Publication and exact next action

Completed work pushed to `origin/fix/lifecycle-2026-10-28`. Main was fetched again
before push and remained `f368a5b`. The connected GitHub tool opened
[PR #7](https://github.com/tokeniyi/school-delivery-bot1/pull/7) targeting main,
open and unmerged. Initial published head: `ab6d87579f2c6325011e821b096785d927305df6`
(validation/handoff commit). This final documentation commit records publication.
P0–P5 are complete; no additional application changes followed final validation. Next action: review the
implementation PR and its migration/locking design. Production rollout and any
legacy-data reconciliation require separate authorization; do not deploy or merge
as part of this task. A fresh task should fetch origin, verify the branch/head and
clean status, then read current progress, contract, plan and this report.
