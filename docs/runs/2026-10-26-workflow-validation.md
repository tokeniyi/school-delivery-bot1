# Development workflow validation — 2026-10-26

## Repository and workflow evidence

- Repository: `https://github.com/tokeniyi/school-delivery-bot1.git`.
- Initial clean branch: `work`; initial commit:
  `cd0b905956163620bde146cf2ffc8736a0190224`.
- Created local `main` tracking `origin/main`, then
  `review/workflow-validation-2026-10-26`. A successful fetch confirmed the same
  main SHA; no application work was performed on main.
- PR base: `main`. The requested `<BASE_BRANCH>` was an unfilled placeholder;
  main was selected because it was the explicitly requested starting branch.
- Read README, `.github/instructions/INSTRUCTIONS.md`, architecture, refactor notes,
  migration chain and tests. No existing AGENTS.md, plan, progress or run reports
  were present. Existing instructions/content were retained.
- Plan was written before implementation. No live polling, webhook deletion,
  Telegram messages, bot container startup, deployment or merge was performed.

## Fixed application defects

### A1 — Unescaped user input in HTML messages (medium)

References: `bot/client.py:8`, `bot/handlers/admin.py:38`,
`services/notifications.py:93`, `bot/handlers/student.py:153`,
`bot/handlers/parent.py:153`; regressions in `tests/test_workflow_regressions.py`.

Expected: names, items and locations display literally and valid requests receive
receipts and review cards. Actual before fix: `Books & <unknown> <b>literal</b>`
was inserted unescaped into cards and receipts inheriting the bot's HTML parse
mode. Supported tags alter display; unsupported tags can cause Telegram parsing
failure. Failed receipts happen after persistence/FSM clearing; failed admin sends
are retried then swallowed. No Telegram request was made to prove this: the exact
unsafe outgoing payload and inherited parse mode were captured locally.

Fix: escape all nine dynamic fields in each admin card; explicitly use
`parse_mode=None` for student/parent submission receipts. Four regression cases
failed before the fix and pass afterward. Existing template HTML is retained.

### A2 — Equal calendar dates persisted in incompatible forms (medium)

References: `bot/handlers/student.py:124`, `bot/handlers/parent.py:103`,
`services/matching.py:50`.

Expected: accepted calendar dates match independently of input padding.
Actual: Python `strptime('%Y-%m-%d')` accepts `2099-1-2`, but handlers saved that
string while SQL compares dates as trimmed strings. `2099-1-2` and `2099-01-02`
therefore fail matching. Two handler regression cases captured the noncanonical
FSM/save values before the fix. Both pass with `parsed_date.isoformat()`.
This fixes new submissions; existing noncanonical stored dates are not migrated.

## Test defects repaired

- `tests/conftest.py:36`: function-scoped fixture loops, session-scoped async tests,
  pooled connections and the synchronous E2E wrapper produced logged
  `RuntimeError: ... Future ... attached to a different loop` during regression
  setup. A green assertion count alone hid those errors. Use a session loop for
  cleanup, dispose pooled connections at teardown and run E2E on pytest's loop
  (`tests/test_end_to_end.py:26`). Final logs have no loop/connection-close errors.
- `tests/conftest.py:18`: notification imports previously occurred before default
  environment setup, making defaults ineffective for import-time configuration.
  Move the import below defaults. Command environment still uses a dummy token.
- `tests/conftest.py:51`: include audit logs in destructive local test cleanup.
  Use a fresh, automatically installed fake notification bot for every test and
  monkeypatch restoration so manually assigned fakes cannot leak across tests.
- `tests/test_notifications_failure_async.py:10`: `assert True` did not verify
  retries or continuation. Now assert three attempts for the failing admin, one
  send to the next admin, and the final failure log.
- An intermediate run failed at collection because `loop_scope` was incorrectly
  passed to `pytest.fixture`; corrected to `pytest_asyncio.fixture`. This was an
  implementation mistake, not an application/environment defect.

## Confirmed deferred application findings

Reproductions below ran using CRUD functions on a new scratch PostgreSQL database,
without notifications. The scratch database was removed afterward. No failing
known-bug tests were added to the permanent suite. These require a separate plan
because status transitions, history, locking and possibly schema policy interact.

### L1 — Conflicting approvals for the same request (high)

References: `database/crud.py:269`, especially the check of only `match.status`;
`database/models.py:97` enforces pair uniqueness, not resource exclusivity.

Expected: once a request is approved, another candidate cannot promise the same
request to a different traveler. Actual reproduction:

1. Create one student request R and two matching travels T1/T2.
2. Persist M1=(R,T1) and M2=(R,T2).
3. `approve_match(session, M1.id, admin_id=123456789)` succeeds.
4. `approve_match(session, M2.id, admin_id=123456789)` also succeeds.
5. Query reports **two approved match rows for R**.

This is reproducible sequentially; concurrent approve/reject has additional risk
because review uses read/check/write without locking or a conditional transition.
Concurrent interleavings were not load-tested. First follow-up: establish exclusive
request approval, travel capacity policy, competing candidate invalidation and
atomic review behavior, then write sequential and concurrent regressions.

### L2 — Resubmission mutates approved history (high)

References: `database/crud.py:69`, `database/crud.py:140`.

Expected from service/CRUD documentation: update an active pending request or
available travel; preserve approved delivery details. Actual: both upserts select
the first row by user without a status condition. After L1, resubmitting the
student with changed item/location/school/date returned **the same request ID**,
retained `matched` status and changed the data visible through the approved match.
Parent upsert also resets status to available/unavailable irrespective of approval.
Pending-review candidate details can similarly become stale. Resolve active-row
policy and candidate invalidation together; avoid an isolated status-filter patch.

### L3 — Rejected-pair discovery cannot persist a new match (medium)

References: `services/matching.py:55`, `database/crud.py:213`,
`database/models.py:97`, `migrations/versions/b818d2b571cd_initial_migration.py`.

Expected: discovery returns persistable candidates consistent with the chosen
rejection policy. Actual: for a pending request/available travel with a rejected
match, `find_matches()` returns that exact pair, but `create_match()` returns
`None` because unconditional pair uniqueness also covers rejected rows.
Reproduction: create pair, reject match, call discovery, attempt persistence;
observed pair in candidates and `Match already exists (race-safe skip)` on insert.
Decide whether same-pair reconsideration is allowed and preserve rejection audit
history; align discovery and persistence before changing the constraint.

## Review coverage and remaining areas

| Area | Coverage and result |
| --- | --- |
| Repository, guidance, setup | Branch/SHA/remote verified; instructions and architecture read; Python/dependencies inspected |
| Handlers, states, keyboards | Registration, field validation, role routing, receipts, admin cards, auth checks and callbacks reviewed; HTML/date fixes |
| Services | Matching query, orchestration, notifications/retry, user/request/travel/health boundaries reviewed |
| Persistence | CRUD upserts, pair creation, review statuses, eager loading, models/enums, indexes and audit writes reviewed; lifecycle issues reproduced |
| Migrations | All four revisions and env configuration reviewed; full round trip and metadata comparison passed |
| Tests | All existing test modules inventoried/reviewed for scenarios, active suite executed; six regression cases added; retry assertions strengthened |
| Runtime/deployment | Main startup/shutdown, middleware, config, Dockerfile/ignore, Compose, Fly configuration and troubleshooting reviewed statically; local DB/Redis healthy |
| Documentation | Added required workflow records; corrected README's stale claim that Compose has no Redis; repaired architecture instruction links and documented current boundary gaps |

Remaining: real concurrent review/upsert stress, active-match deletion/cascade
semantics, rejected-pair policy, stale candidate revalidation, Redis outage/startup
behavior, middleware error reply integration, production pool recovery, Telegram
rate-limit/permanent-failure handling and durable notification delivery, full
container build/runtime and production performance. Existing 'concurrency' tests
submit sequentially; 100-row smoke tests do not establish production scalability.
Existing handlers directly access infrastructure despite service abstractions;
this is recorded architectural drift, not corrected by this run. Parent receipts
also always say `Status: Available` even when `can_carry=False` stores unavailable
(static finding at `bot/handlers/parent.py:151`; not separately exercised here).

## Validation results and limits

Use the explicit local/dummy environment in AGENTS.md; never use production data.
Tests delete rows. Local Python: **3.11.17**, pytest **9.1.1**,
pytest-asyncio **1.4.1**. No `.env.local` override was present in this checkout.

| Check | Result |
| --- | --- |
| Baseline `python -m pytest -q -rs` | **38 passed, 1 skipped**, 11.78s |
| New regressions before app fixes | **6 failed**, 0.58s: two date, two receipt, two card cases |
| Full suite after app/loop fixes | **44 passed, 1 skipped**, 11.74s |
| Final suite after retry assertions | **44 passed, 1 skipped**, 12.51s |
| `alembic heads` / `current` | Single head **5196523efe8d**, local DB at head |
| `alembic check` | No new upgrade operations detected |
| Fresh upgrade, check, downgrade base, re-upgrade, check | All passed on scratch DB; removed afterward |
| `uv pip check --python /workspace/schoolbridge-venv/bin/python` | 40 packages checked; compatible |
| `python -m compileall -q bot database services migrations tests config.py main.py` | Passed |
| `git diff --check` | Passed |
| Docker service inspection | PostgreSQL 16 and Redis 7 already healthy; bot not started |
| CI / lint / type check | No configured workflows or commands found; not claimed as run |
| Full container build/live bot/production checks | Not run; bot/live Telegram work excluded by request |

Skip explanation: `tests/test_additional_flows.py:3` calls
`pytest.skip('moved to split tests', allow_module_level=True)`. Pytest counts the
entire module as one skip. The replacement modules are
`test_rejection_flow_async.py`, `test_duplicate_prevention_async.py`,
`test_admin_access_control_async.py` and `test_notifications_failure_async.py`.
The obsolete module uses outdated matcher APIs and should not be re-enabled as-is.

Expected ERROR-level notification logs come from simulated failures and are
asserted; they are not live Telegram failures. One restricted-shell baseline
attempt stalled on isolated localhost and was terminated, then rerun successfully
with approved environment access. Restricted-shell Git/Docker attempts similarly
failed before approved execution succeeded. Those are environment problems.

## Publication and handoff

GitHub CLI reports the inherited `GH_TOKEN` invalid; runtime configuration reports
no outbound GitHub identity. See `docs/progress.md` for actual push/PR outcomes,
active branch, and exact next action. No credentials were printed or changed.
Follow-up work should first resolve L1/L2 with an explicit lifecycle plan rather
than expand the HTML/date fix into a partial concurrency redesign.
