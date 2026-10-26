# Continuity validation and lifecycle planning — 2026-10-26

## Scope and verified provenance

Repository: `tokeniyi/school-delivery-bot1`. This is a distinct follow-up to
[the earlier workflow run](2026-10-26-workflow-validation.md), not a replacement.
Dates use the user's Africa/Lagos timezone.

Initial checkout `/workspace/school-delivery-bot1`: clean `work` branch at
`cd0b905956163620bde146cf2ffc8736a0190224`; origin is
`https://github.com/tokeniyi/school-delivery-bot1.git`. No reset, stash, overwrite,
or modification of unrelated tracked work was performed.

The restricted-shell `git fetch origin` failed with proxy connection refusal.
Approved execution succeeded. The checkout's default fetch did not populate the
review branch, so an explicit fetch was required:

```bash
git fetch origin refs/heads/review/workflow-validation-2026-10-26:refs/remotes/origin/review/workflow-validation-2026-10-26
git rev-parse origin/review/workflow-validation-2026-10-26
```

Verified remote head: **`07876104813e405e284eb51d38d43df395cf8fe2`**, matching
GitHub PR #4 metadata. Its two commits are `0062814` (fixes/tests/docs) and
`0787610` (publication/handoff docs). PR #4 is open, not draft, unmerged, targets
`main` at `cd0b905`, and had no discussion/review comments in the fetched timeline.
GitHub's generated merge SHA is not the source branch head.

Created a detached worktree at `work/continuity` from the verified remote head
for baseline validation; only afterward created
`plan/lifecycle-continuity-2026-10-26` explicitly at that same full SHA.
The original checkout remains on `work`.

Read AGENTS.md, README, existing contributor instructions, architecture,
implementation plan, progress and the referenced run report. Examined current
CRUD, models/enums, discovery, lifecycle services, relevant handlers, tests,
configuration and migration chain. Reported reconstruction and gaps in chat
before edits. No agent delegation was used.

## Reconstructed prior run

Completed: escaped dynamic admin HTML fields, plain-text submission receipts,
canonical accepted dates; six regressions; session-loop/fake-bot/audit cleanup
repairs; notification retry/continuation assertions; contributor rules and handoff
records; corrected Redis documentation. PR #4 published those changes.

Recorded then: baseline 38 passed/1 skipped, six failures before application fixes,
final 44 passed/1 skipped (12.51s), migration head `5196523efe8d`, no schema drift,
fresh migration round trip, compatible dependencies, compilation and whitespace.
The six red-before-fix outcomes are historical evidence; this run did not revert
application code to repeat them or rerun the old main baseline.

Not verified then: real concurrent lifecycle transactions, Redis failure/recovery,
middleware integration, full container build/runtime, production pool/performance,
live Telegram behavior or durable notification delivery. Existing sequential
“concurrency” tests and small smoke data did not establish those properties.
These gaps remain after this continuity run.

Outstanding: L1 conflicting approvals, L2 approved-history mutation, L3 rejected-pair
discovery/persistence disagreement. The prior exact next action was a focused L1/L2
plan, then sequential resubmission/conflict regressions and true concurrent coverage.
This run completes only the continuity and planning portions.

## Disposable baseline reproduction

Used new local containers `continuity-pg-20261026` (`postgres:16-alpine`) and
`continuity-redis-20261026` (`redis:7-alpine`), with no existing volumes mounted.
Bound only loopback ports 55432 and 56379. Existing schoolbridge service containers
and their data were untouched. Redis persistence disabled. No bot container started.
Neither `.env` nor `.env.local` existed in the validation worktree. Explicit command
environment replaced all configured application service URLs and bot credentials:

```bash
export BOT_TOKEN=123456:TESTTOKEN
export ENVIRONMENT=development
export DATABASE_URL=postgresql+asyncpg://postgres:continuity_test@127.0.0.1:55432/continuity
export REDIS_URL=redis://127.0.0.1:56379/0
export ADMIN_IDS=123456789
export PATH=/workspace/schoolbridge-venv/bin:$PATH
mkdir -p work
alembic upgrade head
alembic heads
alembic current
alembic check
alembic downgrade base
alembic upgrade head
alembic check
python -m pytest -q -rs --log-file=work/continuity-tests.log
python -m compileall -q bot database services migrations tests config.py main.py
uv pip check --python /workspace/schoolbridge-venv/bin/python
git diff --check
```

Local-service commands needed approved execution because of shell isolation.
Only disposable services were contacted by validation. No production URLs/data,
polling, webhook operations, Telegram messages, deployment or merges were used.
The suite uses fake messages and the autouse fake notification bot with dummy token.

| Check | Current result |
| --- | --- |
| Python | 3.11.17 |
| Full suite at exact PR #4 head | **44 passed, 1 skipped in 10.52s** |
| Skip | `tests/test_additional_flows.py:3`, module-level “moved to split tests”; retained |
| Test log inspection | Expected simulated notification errors only; no different-loop or connection-close errors |
| Migration head/current | `5196523efe8d`, single head |
| Fresh upgrade/check/downgrade base/re-upgrade/check | Passed, no new upgrade operations |
| Dependency consistency | 40 packages checked, compatible |
| Compilation and whitespace | Passed |
| Disposable Redis PING | True; not an FSM/outage integration test |
| CI/lint/type checks | No configured commands/workflows; not claimed |
| Original six red tests and main's 38-pass baseline | Historical results only, not rerun |
| Concurrency, production and full bot/container runtime | Not tested |

An ignored scratch script additionally exercised CRUD with synthetic users and
new request/travel rows, without notification calls. Results:

- L1: two candidates for one request both approved; approved-row count **2**.
- L2 request: resubmission returned the same ID, retained `matched`, changed item.
- L2 travel: resubmission returned the approved travel ID, reset to `unavailable`.
- L3: rejected pair appeared in `find_matches()`; `create_match()` returned `None`
  with the expected duplicate-pair warning.

These confirm existing defects; no known-bug tests or application fixes were added.
Both disposable containers and their anonymous data volumes were removed afterward.

## Documentation/code/PR inconsistencies

1. Service/CRUD docs promise pending-request/available-travel upserts, but code
   selects the first row for the user regardless of status. Approved delivery
   details can change in place. This is L2, not a completed fix.
2. Pair uniqueness prevents duplicate pairs, not request allocation conflicts.
   Review checks only match status; rejection resets resource statuses without
   checking other approvals. Atomicity across competing transactions is unproven.
3. Discovery excludes pending/approved pairs only; persistence uniqueness includes
   rejected rows. Reconsideration policy remains undecided (L3).
4. Architecture's old SQLite test example conflicts with PostgreSQL-specific
   asyncpg cleanup. Use AGENTS.md's disposable PostgreSQL recipe. README's tree
   comment says 5 requests/minute, whereas its troubleshooting text and middleware
   use 15 messages/10 seconds. These older documentation issues are recorded here;
   this planning task does not broaden into unrelated corrections.
5. Parent receipt always says Available even for `can_carry=False`; prior run
   recorded it statically. Existing boundary drift also remains disclosed.
6. README's production-focused description is not production validation evidence.
   PR #4 accurately describes its bounded fixes and deferred issues. Its current
   head includes the documented follow-up publication commit; the older `0062814`
   SHA in historical text is not the current head. No PR publication mismatch found.
7. The initial local `work` checkout was at main's old base, not the handoff branch.
   Explicit fetch and a separate exact-head worktree resolved this without resetting it.

## Planning outcome, blockers and next action

Added [focused lifecycle plan](../lifecycle-implementation-plan-2026-10-26.md),
linked from the retained original implementation plan, and updated progress with
an explicitly current handoff while preserving the previous run's record.
No application, migration, dependency or test source files changed.

Established invariants: request exclusivity, approved-history preservation, atomic
review/audit and revalidation of current candidate eligibility. Product decisions
still missing: travel capacity, competing-candidate disposition, active-row and
resubmission/edit policy, rejected-pair reconsideration, and reconciliation of any
existing conflicts. No policies or production repair actions were invented.
Those decisions block dependent implementation, not publication of this plan.

Exact next action: review this documentation PR and PR #4 without merging; obtain
product answers from the plan's decision table. In a new implementation task,
refresh/reverify the agreed remote base, write failing sequential conflicting-
approval and approved-history resubmission regressions before application changes,
then add truly overlapping PostgreSQL transaction coverage.

## Publication outcome

Committed the four documentation files as
`8a58b9250989544116a9ea361d1c9ecfd8ee534a` and pushed
`plan/lifecycle-continuity-2026-10-26`. Remote inspection confirmed the planning
commit and unchanged PR #4 head. The connected GitHub tool opened
[PR #5](https://github.com/tokeniyi/school-delivery-bot1/pull/5), targeting
`review/workflow-validation-2026-10-26`, with the PR #4 dependency explicit.
This subsequent documentation commit records the publication link. Local Markdown
links and staged whitespace checks passed; the diff contains only the plan,
progress, historical-plan follow-up link and this report. PR #4 and PR #5 remain
open and unmerged. No CLI authentication changes were needed.
