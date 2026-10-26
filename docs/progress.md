# Progress — 2026-10-26

## Active work

- Repository: `tokeniyi/school-delivery-bot1`.
- Branch: `review/workflow-validation-2026-10-26`.
- Base/PR target: fetched `main` at `cd0b905956163620bde146cf2ffc8736a0190224`.
- Scope and phases: [implementation-plan.md](implementation-plan.md).
- Findings/evidence/coverage: [dated run report](runs/2026-10-26-workflow-validation.md).

## Completed

Repository and clean starting state confirmed; project instructions, architecture,
migrations and tests reviewed; baseline reproduced. Fixed literal text rendering
and date normalization with six red-before/green-after regressions. Repaired test
loop/fake isolation and audit cleanup; strengthened notification retry assertions.
Required guidance and handoff records added, preserving existing content.
README Redis guidance and architecture links/implementation caveats corrected.

## Validation

- Baseline: **38 passed, 1 skipped** (legacy module moved to split tests).
- New regression cases before fixes: **6 failed**, as expected.
- Final full suite: **44 passed, 1 skipped**, **12.51s**.
- Migration head/current/check: **5196523efe8d**, no schema drift.
- Scratch database: full upgrade/check/downgrade/re-upgrade/check passed; removed.
- Dependency consistency, Python compilation and whitespace checks passed.
- No configured CI, lint or type-check command; container build and live services
  beyond local DB/Redis inspection were not exercised.
- No polling, webhook deletion, live Telegram messages, deployment or merge.

## Blockers and deferred work

No publication blocker remains. Application/test/documentation commit
`0062814a2a64dc2dd1eec6e57c0e02f97f23a90e` was pushed successfully. GitHub CLI
reported invalid `GH_TOKEN` and PR creation returned GraphQL `Forbidden`; the
connected GitHub tool successfully created [PR #4](https://github.com/tokeniyi/school-delivery-bot1/pull/4)
against `main`. PR is open and unmerged. This progress update is a subsequent
documentation commit on the same branch. Environment sandbox isolation was
resolved through approved execution for local DB, Docker inspection and fetch.

Confirmed deferred defects: conflicting request approvals, approved-record
mutation by upserts, and rejected-pair discovery/persistence disagreement. Further
coverage remains for concurrent lifecycle transitions, Redis failures, middleware,
production deployment/performance and notification durability. See the run report.

## Exact next action

Review [PR #4](https://github.com/tokeniyi/school-delivery-bot1/pull/4) without merging.
For a new coding task, read AGENTS.md, this document, plan and report, then:

```bash
git fetch origin
git switch review/workflow-validation-2026-10-26
git status --short --branch
git log -2 --oneline
```

The working tree should be clean and HEAD should match the remote working branch.
First implementation action: write a focused L1/L2 lifecycle plan covering request
exclusivity, travel capacity policy, competing pending candidates, atomic admin
review, and preserving approved history. Then add sequential conflicting-approval
and resubmission regressions before changing code; add true concurrent transaction
coverage. Do not merge this PR or start live polling/messages as part of that task
without new instructions. The CLI auth problem does not prevent using the connected
GitHub tool for authorized PR work.
