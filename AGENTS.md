# Contributor and agent guidance

## Project rules

Read [README.md](README.md), [.github/instructions/INSTRUCTIONS.md](.github/instructions/INSTRUCTIONS.md),
[docs/architecture.md](docs/architecture.md), migrations and affected tests before editing.
The existing instructions remain authoritative; `.github/instructions/agents.md.instructions.md`
is currently empty. Preserve existing content when updating documentation.

Keep Telegram input/routing in handlers, workflow orchestration in existing services,
and persistence in `database/crud.py`. Reuse existing abstractions; flag current
boundary violations rather than extending them. Use async SQLAlchemy, canonical
status enums, timezone-aware timestamps and Alembic for schema changes. Do not
use `create_all()` in production. Add no unrelated features.

Treat user text as literal: escape values embedded in HTML and explicitly disable
parse mode for plain-text receipts. Normalize accepted dates with `isoformat()`.

## Branch workflow

1. Inspect `git status --short --branch`, `git remote -v`, `git log -1` and fetch
   origin. Preserve unrelated changes. Record any fetch failure.
2. Start from `main` (or the explicitly requested base), confirm starting SHA and
   create a separate descriptive branch. Never work directly on main or force push.
3. For complex changes write `docs/implementation-plan.md` before implementation.
   Add behavioral regressions; demonstrate failure before the application fix.
4. Update `docs/progress.md` and a dated report in `docs/runs/`, including coverage,
   deferred findings, failed/skipped/unavailable checks and exact next action.
5. Review diff, commit, push the working branch and open a PR against the agreed
   base. Do not merge. If unavailable, preserve committed work and record the error.

## Safe, verified validation

Python 3.11.17; this environment's interpreter is `/workspace/schoolbridge-venv/bin/python`.
Elsewhere activate a Python 3.11+ virtualenv with `requirements.txt` installed.
These commands were verified on 2026-10-26 from the repository root:

```bash
# Use only a disposable LOCAL PostgreSQL database: tests DELETE application rows.
# Check that .env.local is absent or points at the same disposable services;
# config.py loads it with override=True, overriding even command environment values.
export BOT_TOKEN=123456:TESTTOKEN
export ENVIRONMENT=development
export DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/schoolbridge
export REDIS_URL=redis://localhost:6379/0
export ADMIN_IDS=123456789
export PATH=/workspace/schoolbridge-venv/bin:$PATH  # adapt to your virtualenv
python -m pytest -q -rs --log-file=work/tests.log
alembic heads
alembic current
alembic check
python -m compileall -q bot database services migrations tests config.py main.py
git diff --check
uv pip check --python /workspace/schoolbridge-venv/bin/python
```

Create `work/` before using log paths; it is ignored scratch space. Local PostgreSQL
and Redis were already running and healthy; do not start the bot service. The
command sandbox needed approved access to local services and the configured proxy.
A connection failure there is an environment limitation, not a failed assertion.

`alembic upgrade head`, `alembic downgrade base`, `alembic upgrade head`, then
`alembic check` were verified on a newly created scratch PostgreSQL database.
Never run downgrade or test cleanup against shared/production data. There are no
configured CI workflows or lint/type-check commands in this checkout.

The pre-lifecycle baseline was **44 passed, 1 skipped**. Read `docs/progress.md`
for the current lifecycle suite and migration validation results. The skip at
`tests/test_additional_flows.py:3` disables an obsolete module, not one active
scenario. Rejection, duplicate prevention, admin authorization and notification
failure scenarios have split replacements. Keep this module skipped until its
obsolete APIs are reconciled; do not blindly re-enable it.

Never run `python main.py`, compose up the bot, poll Telegram, delete webhooks,
or send messages during a review unless explicitly authorized. Use fake messages,
a fake notification bot, and dummy bot credentials. Do not run `tests2/diagnose_env.py`:
it prints credentials. Do not commit `.env`, local overrides, logs or credentials.

## Resume work

Read `docs/progress.md`, the latest dated report, and the implementation plan first.
Verify branch/SHA and a clean tree, then execute the recorded next action. Distinguish
fixed application defects, test repairs, environment blockers and deferred findings.
Do not infer that a passing suite proves concurrency safety or production readiness.


## Lifecycle changes (2026-10-28)

Use `docs/lifecycle-decisions-2026-10-28.md` for confirmed policies. Do not copy
historical unresolved decisions or next actions from earlier reports. Migration
`a28c10` must fail on existing conflicting approvals; never automatically reconcile
production data. Downgrade refuses to discard new lifecycle events. Migration tests
create/drop fresh scratch databases on the explicitly configured disposable local
PostgreSQL instance and require database-creation privileges.
