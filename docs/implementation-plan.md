# Workflow validation implementation plan

## Scope (2026-10-26)

Start from fetched `main` at `cd0b905956163620bde146cf2ffc8736a0190224`.
Use `review/workflow-validation-2026-10-26`; target PR at `main` (the request's
`<BASE_BRANCH>` is an unresolved template; main is the stated starting branch).
Preserve the four-layer architecture and existing async SQLAlchemy / aiogram conventions.
No live polling, Telegram messages, deployment, or new features.

## Phases

1. Confirm clean repository, read instructions, architecture, migrations and tests;
   establish baseline using local disposable PostgreSQL and dummy bot credentials.
2. Review handlers, services, persistence, configuration and deployment wiring.
   Record confirmed bugs separately from test defects and environment limitations.
3. Add regressions for HTML metacharacters in admin cards and submission receipts,
   and accepted unpadded dates. Run against unchanged application code to prove failure.
4. Escape each dynamic field in HTML review cards; use explicit plain text for
   submission receipts. Canonicalize parsed dates with `date.isoformat()` before
   saving FSM data. Keep persistence ownership and matching rules unchanged.
5. Repair bounded test isolation issues (environment defaults before imports,
   fake bot restoration, audit-log cleanup); verify suite and migration checks.
6. Update guidance, progress and dated report; review diff, commit, push, open PR.

## Completion criteria

Baseline and skip reason recorded; regression failures reproduced before fixes;
relevant checks pass after fixes; remaining risks have evidence and next steps;
required documents preserve existing guidance; clean committed working tree;
branch pushed and PR opened, or exact external blocker and recovery commands saved.

## Deferred scope

Match review concurrency, conflicting candidate lifecycle, edits to historical or
pending matched records, rejected-pair rematching policy, architectural boundary
cleanup, notification durability, and production deployment need separate focused
plans. Do not expand this run into a lifecycle redesign.

## Completion (2026-10-26)

Phases 1–6 complete. Baseline 38 passed/1 skipped; six regressions failed before
the fixes; final 44 passed/1 skipped. Migration round trip, metadata, dependency,
compilation and whitespace checks passed. Changes committed and pushed;
[PR #4](https://github.com/tokeniyi/school-delivery-bot1/pull/4) targets main and
was open at publication and merged on 2026-10-26. CLI auth failure was resolved
for publication by using the
connected GitHub tool. Remaining lifecycle defects and review gaps are documented.

## Continuity follow-up (2026-10-26)

The PR #4 plan above remains complete. Continuity validation reproduced its current
44-pass/1-skipped baseline at remote head `0787610`; no application fixes were made.
The handoff's next planning action is now recorded in the separate
[focused L1/L2 lifecycle plan](lifecycle-implementation-plan-2026-10-26.md).
See the [distinct continuity report](runs/2026-10-26-continuity-lifecycle-planning.md)
for current branch, validation and unresolved decisions. That plan is not approval
to implement product policies or merge either PR.

## Main integration follow-up (2026-10-27)

PR #4 merged into main at `6772ea1`. PR #5 later merged into the review branch
at `00e410a`, so its planning documents were absent from main. A new branch from
fetched main imports only PR #5's documentation changes and corrects publication
status, preserving the original plans and unresolved product decisions. See the
[current progress record](progress.md) and
[integration report](runs/2026-10-27-planning-docs-main-integration.md).
No lifecycle implementation, service validation rerun or merge is part of this task.
