# Focused L1/L2 lifecycle implementation plan — 2026-10-26

## Status and dependency

Planning only; no application, schema or test changes are authorized by this plan.
Original base: PR #4 head `07876104813e405e284eb51d38d43df395cf8fe2`.
PR #4 merged into main on 2026-10-26; PR #5 subsequently merged this plan into
`review/workflow-validation-2026-10-26` on 2026-10-27, not into main.
This document is now being integrated through a separate PR from
`docs/integrate-lifecycle-plan-2026-10-27` to main, based on
`6772ea12ee7e01bd8666590f6e67d59087450ef9`. See the
[integration report](runs/2026-10-27-planning-docs-main-integration.md).
Do not merge the integration PR or implement lifecycle fixes as part of this task.
The requirements and unresolved decisions below are unchanged by integration.

Read [progress](progress.md), [original review](runs/2026-10-26-workflow-validation.md)
and [continuity validation](runs/2026-10-26-continuity-lifecycle-planning.md).
The earlier [implementation plan](implementation-plan.md) remains the historical
record for PR #4; this is the focused follow-up it requested.

## Established requirements and evidence

- **Request exclusivity (L1):** an approved request must not be promised to another
  traveler. The prior review explicitly states this invariant; the current CRUD
  allows two sequential approvals for one request, reproduced again in continuity.
  Pair uniqueness in `database/models.py` protects only identical pairs.
- **Approved history (L2):** subsequent submissions must preserve approved delivery
  details and associations. Request/travel service and CRUD documentation promise
  pending/available-row updates; both upserts actually select the first row by
  user without status filtering. Continuity reproduced mutation of a matched
  request and resetting an approved travel to unavailable.
- **Atomic review:** review eligibility, resource eligibility, status changes,
  timestamps and audit writes must succeed together or leave no partial changes.
  A stale or competing review must not undo an approved allocation. Current
  approve/reject code checks only the candidate's status and uses read/check/write.
  Existing enums and timezone-aware timestamps remain the conventions.
- **Candidate validity:** discovery and persistence must agree on eligibility;
  admin review must revalidate the current request/travel details and availability.
  Editing a source row must not silently change the delivery the admin approved.
- **Compatibility:** retain PR #4's literal text/date behavior, admin authorization,
  pair duplicate protection and fake-bot test isolation. Keep polling and live
  Telegram outside implementation validation unless separately authorized.

These requirements do not establish one-package travel capacity, the number of
active submissions allowed per user, or how superseded candidates should be named.

## Unresolved product decisions — resolve before dependent implementation

| Decision | What is known | Required answer and consequence |
| --- | --- | --- |
| Travel capacity | `can_carry_packages` is boolean; approval sets travel to matched; no numeric capacity exists | Is a travel exclusive to one request or may it carry several? If several, define units, limit and availability transitions before designing capacity constraints. Do not assume a one-request limit. |
| Competing pending candidates | Multiple candidates may reference one request or travel | On approval, should competitors be closed immediately or remain visible but non-approvable? Define terminal reason/status, audit and admin display. For travel competitors this depends on capacity. Never label automatic invalidation as an admin rejection without agreement. |
| Active-row selection and resubmission | Service docs permit updating pending requests/available travels; approved history must survive | Define how to identify the editable row if several exist, whether an unavailable travel is editable, and whether a resubmission after approval creates a new row or is refused. Do not select an arbitrary first row. |
| Edits while awaiting review | Candidates reference mutable source rows without a version/snapshot | Are edits blocked, or do they invalidate/version pending candidates and trigger rediscovery? Define what the admin must see and approve after a change. |
| Same-pair reconsideration (L3) | Discovery returns rejected pairs; unconditional pair uniqueness prevents insertion | Is reconsideration allowed, and under what explicit action? Preserve rejection audit history. If forbidden, exclude rejected pairs; if allowed, choose an explicit review-attempt/history model. Do not drop the constraint alone. |
| Existing inconsistent records | Synthetic reproductions prove defects; production data has not been inspected | Who resolves pre-existing conflicting approvals, and what is the approved reconciliation process? Never auto-select a winner or rewrite history. Any production audit/repair needs separate authorization. |

No default answer is adopted here. L3 policy is an adjacent dependency where it
intersects candidate invalidation; otherwise keep its implementation separate.
Cancellation, completion, deletion/retention and historical user-profile snapshots
need separate scope if requested; do not invent them to solve L1/L2.

## Ownership and boundaries

| Concern | Owner / entry points | Persistence and integration |
| --- | --- | --- |
| Review workflow | `MatchingService.approve_match/reject_match`, called by admin callbacks | Transaction operations in `database/crud.py`; `Match`, request, travel and `AuditLog` |
| Submission workflow | `StudentRequestService.register_request`, `ParentTravelService.register_travel`, called by FSM handlers | CRUD upserts and explicit active-row selection/history preservation |
| Discovery | `MatchingService.trigger_automatic_matching`, `services/matching.py` | Align query and `create_match` with the approved lifecycle contract |
| Notification | Existing notification helpers after committed successful transitions | Fake bots during tests; durable delivery remains deferred |

Keep policy out of Telegram handlers and SQLAlchemy implementation out of the
interface. Record current direct infrastructure access as existing drift; do not
expand it or create a parallel lifecycle service. Update architecture documentation
alongside any eventual ownership, schema or transition changes.

## Future implementation sequence (requires a new implementation task)

1. **Ratify the contract.** Record answers above, a transition table and operation
   outcomes (success, stale/already processed, conflict, ineligible). Specify which
   competing rows change, which remain untouched, and which submissions are editable.
   Do not treat this plan as approval of a particular capacity or rematching policy.
2. **Write failing sequential regressions first.** One request/two travels: approving
   the second candidate cannot produce a second approved allocation. Approve one
   then reject a competitor: the approved request remains matched. Resubmit both
   parties after approval: approved IDs, delivery fields and association stay intact;
   assert the newly agreed create/refuse behavior separately. Edit pending candidates
   and assert the agreed stale-review outcome. Assert audit count and unchanged
   unrelated records, using fresh sessions to avoid identity-map artifacts.
3. **Design one transaction boundary.** CRUD currently commits inside each operation;
   make the whole approved transition and its audit atomic. A proposed approach is
   deterministic row locking on the shared request/travel resources, followed by
   reloading/revalidating candidate and source state. Locking only a candidate cannot
   prevent two different candidates from allocating the same request. Use the same
   lock ordering across review, submission and candidate creation to avoid deadlocks.
   Conditional transitions must detect a losing reviewer; rollback must leave no
   status or audit residue. Final lock/constraint design follows the ratified contract.
4. **Add database enforcement and migration only where justified.** Consider a partial
   unique constraint/index for approved request IDs as defense in depth. Travel
   uniqueness is conditional on the capacity decision. Before adding constraints,
   specify a read-only conflict audit and fail safely on existing conflicts; do not
   silently delete or choose records. Preserve pair uniqueness until L3 is resolved.
   Use Alembic, verify upgrade/downgrade/re-upgrade and metadata comparison on scratch
   data. History preservation may require new rows or versions, based on step 1.
5. **Integrate source updates and discovery.** Serialize edits with approval, preserve
   approved delivery fields, and apply the agreed invalidation/version rules in the
   same transaction. Recheck eligibility at candidate persistence and review, rather
   than trusting the earlier discovery query or a stale Telegram review card.
   Rejection must not reset resources owned by another successful approval or
   override an explicit unavailable state. Notify only after successful commit;
   stale/losing attempts produce no success notification or duplicate review audit.
6. **Prove concurrency with PostgreSQL.** Use independent sessions/connections and
   barriers that force overlapping reads/writes; sequential loops and `gather` alone
   are insufficient evidence. Cover two approvals sharing a request, approve versus
   reject on one candidate, approve versus rejection of a competitor, approval versus
   source edit/resubmission, and duplicate submission/discovery. Add shared-travel
   contention according to the capacity decision. Verify committed invariants with a
   third session, bounded completion, rollback behavior and audit counts. Inject a
   transaction failure to prove atomicity. Use fake notifications at service level.
7. **Validate and publish separately.** Retain the 44-pass baseline and documented
   legacy module skip; new regressions must fail before their fixes and pass afterward.
   Run focused and full tests, migration round trip/check, dependency, compilation
   and whitespace checks with disposable services. Update architecture, progress and
   a distinct run report, recording decisions and coverage limits. Open an implementation
   PR against the agreed base; do not merge or deploy without instructions.

## Acceptance and remaining limits

Completion means sequential and truly overlapping transactions preserve the agreed
allocation/history invariants; losing/stale reviews cannot change committed delivery
state or notify success; source edits and rediscovery obey the ratified contract;
audit and schema checks pass. Product-dependent assertions cannot be finalized until
the decisions above are answered. No policy-dependent implementation is authorized
by this planning document.

Redis outage recovery, middleware integration, production pool/performance behavior,
container builds, Telegram rate limits/permanent failures, notification durability,
legacy stored date normalization and deletion/cascade semantics remain deferred.
A passing baseline does not prove these properties.

## Exact next action

Review the main-targeting documentation integration PR without merging it. PRs #4
and #5 are already merged into their respective bases. Obtain the product answers
in the decision table, starting with travel capacity, competing-candidate disposition
and resubmission/edit policy. In a newly authorized implementation task, refresh the
remote heads and write the sequential conflicting-approval and approved-history
resubmission regressions before changing application code; then add real concurrent
transaction coverage as above.
