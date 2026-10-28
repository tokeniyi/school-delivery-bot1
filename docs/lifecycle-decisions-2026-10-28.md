# Confirmed lifecycle contract — 2026-10-28

Authorized user decisions supersede the unresolved choices in the historical
[planning document](lifecycle-implementation-plan-2026-10-26.md). Active implementation
phases and gates are in [implementation-plan.md](implementation-plan.md).

## Requirements

1. A trip carries one student delivery request. A request has at most one approved
   trip. Existing conflicting production approvals are never automatically repaired.
2. Approval closes every other pending candidate sharing either record. Retain the
   candidate and its history; record `allocated_by_match:<winner-id>`. Automatic
   `closed` is distinct from admin `rejected`.
3. Approved request/travel delivery fields and associations survive resubmission.
   A subsequent submission creates a fresh row instead of rewriting approved history.
4. Rejected pairs require explicit configured-admin reconsideration. Keep the same
   candidate ID and append a new review round; never overwrite rejection evidence.
5. The user subsequently confirmed edits while review is pending are allowed:
   close affected candidates and require fresh review. Source rows with candidate
   history are versioned by retaining the old row as `superseded` and inserting
   a replacement. Old candidate details remain readable; matching uses the new row.

## Operations and transitions

| Operation | Preconditions | Atomic result |
| --- | --- | --- |
| Create candidate | Pending request, available willing trip, matching normalized route/school/date, no existing pair | Pending candidate and creation event |
| Approve | Current pending review round and eligible source records | Approved candidate; both resources matched; incompatible pending candidates closed with reason; review/closure events and admin audits |
| Reject | Current pending review round | Rejected candidate and review/audit; no resource-status resets |
| Edit unreviewed draft | One editable pending request/available trip and no candidate history | Update the draft |
| Edit source with candidate history | One editable pending request/available trip | Supersede source, close its pending candidates with `source_edited:<kind>:<id>`, insert replacement; future matching requires fresh review |
| Submit after approval | Historical matched records exist | Insert new request/travel; preserve approved records |
| Reconsider | Actor in configured ADMIN_IDS; rejected candidate; both original source records eligible | Append explicit reconsideration event/audit; pending review at next revision; retain previous rejection/review events |
| Repeat/stale review or reconsideration | Already processed, wrong revision, or ineligible | No successful transition, audit or success notification |

Ordinary matching excludes every existing pair, including rejected and closed
pairs. An edited source has a new ID and therefore yields new candidate pairs;
that is a fresh source version, not reopening an unchanged rejected pair.
Reconsideration only reopens a rejected candidate, not an automatically closed one.

## Entry points and authorization

`/reconsider_match MATCH_ID` follows existing admin command conventions: configured
`ADMIN_IDS` membership, independent of mutable user-role data. The handler and
service guard access; CRUD also checks authorization for explicit reconsideration.
Fresh admin cards are sent only after commit. Review buttons include the current
review revision; legacy buttons identify round 1 and cannot act on later rounds.
Automatic closure sends no misleading admin-rejection message to either party.

## Persistence and transaction ownership

Existing registration services own submissions, MatchingService owns review and
reconsideration orchestration, and database/crud.py owns transaction implementation.
All lifecycle writers acquire User owner-row locks in ascending ID order. Owner
locks cover draft insertion as well as existing resources, preventing concurrent
submissions from creating duplicate drafts. Review/source-edit operations lock
candidate rows in ascending candidate ID order; crossed competitors use that same
order. Eligibility is reloaded after locks, not trusted from stale discovery.
This serializes lifecycle writes per participating user, not globally.

Partial unique indexes on approved request and trip IDs enforce exclusivity even
against writers bypassing the application lock protocol. Existing pair uniqueness
remains. MatchEvent records creation, reviews, automatic closure and explicit
reconsideration; lifecycle code only appends events. AuditLog remains intact.
Migration a28c10 captures known legacy state without inventing actors or absent
transitions; historical audit rows are preserved. A populated lifecycle history
blocks downgrade rather than silently discarding evidence. Empty scratch databases
support the complete migration round trip.

## Remaining scope and decisions

No unanswered policy blocks this implementation's normal lifecycle paths.
Legacy multiple editable rows require an explicit selection/reconciliation policy;
the code raises a clear error instead of selecting the first arbitrarily. The old
documented upsert rule only edits available travels; an unavailable travel is not
silently reactivated by reconsideration. A new submission may create a new record.
Production conflict reconciliation requires separate authorization and human policy.

Cancellation/completion, deletion/retention and mutable user-profile snapshot policy
remain outside this task. Delivery history refers to preserved request/travel fields;
it does not freeze future changes to shared user display names. Durable notification
delivery, production load testing, middleware and Redis outage behavior remain deferred.
