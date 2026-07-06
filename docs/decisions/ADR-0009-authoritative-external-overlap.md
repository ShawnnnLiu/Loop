# ADR-0009: External Calendar Moves May Overlap (Advisory, Not a Rejection)

## Status

Accepted

## Context

Inbound reconciliation (`../specs/calendar-reconciliation.schema.md`) adopts a
user's calendar-side move only when the whole resulting placement passes the
same **hard** rules as drag-to-adjust. Overlap — with another proposed block or
with a fixed busy interval — was one of those hard rules
(`NO_VALID_CONTIGUOUS_BLOCK`).

In dogfooding that produced a dead-end: the user dragged a Loop event on their
Google Calendar onto another block — deliberately double-booking themselves
(e.g. planning to review flashcards during a slow meeting). Reconcile rejected
the move ("no open block long enough at the new time") and the only exit
offered was a full replan. But the edit **already happened** on the user's own
calendar: reconciliation is read-only, so rejecting it undoes nothing — it just
leaves the plan out of sync with the calendar the user just edited, and demands
a rebuild to converge.

Constraints that shape the fix:

- The external calendar is the one surface where the user can see *everything*
  (Loop's events and their own meetings side by side). A move made there is the
  most informed placement decision in the system.
- ADR-0008 already established the tier split: a manual placement override
  relaxes what is a *quality preference*, not a *safety rule*, and surfaces a
  heads-up instead of a wall. Overlap on a calendar-side move is the same
  class: the user is asserting they can do both things, and no calendar write,
  approval gate, or safety invariant is involved in believing them.
- Rejection must stay meaningful: allowed-hours and daily-load are user-stated
  *policy bounds*, not placement preferences, and remain grounds to reject.

## Decision

Overlap becomes **advisory** for external reconciliation moves. In-app
drag-to-adjust keeps the hard overlap rule. Both stay deterministic.

1. **Reconciliation adopts overlapping moves.** The shared placement validator
   (`scheduler/adjustment.py`, `validate_placements`) gains a keyword-only
   `overlap_advisory` mode, used **only** by the reconciliation path. In that
   mode both overlap gates — overlap with a fixed busy interval and overlap
   with another proposed block — emit a non-blocking `OVERLAP_ADVISORY`
   warning instead of a hard `NO_VALID_CONTIGUOUS_BLOCK` conflict.
2. **Both sides of a block-vs-block overlap warn.** In advisory mode the
   pairwise gate warns *both* tasks in the pair, so the advisory attaches to
   whichever side the user actually moved (the unmoved side's warning simply
   never lands on a delta).
3. **The adopted delta carries the heads-up.** An adopted move/resize may now
   carry `OVERLAP_ADVISORY` as its `reason_code`. When a move earns both
   advisories, `DEPENDENCY_ADVISORY` takes precedence: the overlap is visible
   on the calendar grid itself, prerequisite ordering is not.
4. **In-app drag is unchanged.** Pre-approval, the draft is not on the
   calendar yet, the client's rendering is untrusted, and a clean slot can
   still be chosen cheaply — the hard overlap refusal stays. The two doors are
   honestly different: one edits a *proposal*, the other reports an edit that
   *already exists* on the user's own calendar.
5. **Rejection stays reserved for policy bounds.** On the reconcile path a
   `rejected` delta now only ever carries `OUTSIDE_ALLOWED_HOURS` or
   `DAILY_LOAD_EXCEEDED`. `NO_VALID_CONTIGUOUS_BLOCK` remains in the
   contract's rejected-delta vocabulary (`ADJUSTMENT_REASON_CODES`) — it is
   still the in-app drag refusal code and historical reconciliation results
   carry it — but the reconcile producer no longer emits it.
6. **An adopted overlap is a display state, not an error.** The week grid
   renders overlapping blocks stacked side-by-side (Google-Calendar style), so
   the adopted placement is legible rather than drawn as a collision.
7. **Not an external conflict.** An adopted-with-`OVERLAP_ADVISORY` delta is
   the user's own placement: like `DEPENDENCY_ADVISORY` (ADR-0008) it never
   feeds the drift classifier's `external_conflict_task_ids` input and emits
   no `DRIFT_EXTERNAL_CONFLICT`.

## Consequences

- The reported dead-end is gone: a calendar-side move onto another block is
  adopted with a heads-up, the plan converges to the calendar, and no rebuild
  is demanded.
- `OVERLAP_ADVISORY` is a new **non-blocking** `reason_code`. Clients must
  treat it on an `adopted` delta as informational.
- The internal draft may now legitimately contain overlapping entries. The
  draft-schedule contract never forbade overlap (its invariants are tz-aware
  times, `end > start`, unique task ids, non-empty), and adjustment is only
  allowed pre-approval — before adoption can have introduced an overlap — so
  no other validation surface is affected.
- Specs updated: `../specs/calendar-reconciliation.schema.md` (adopted may
  carry `OVERLAP_ADVISORY`; overlap no longer rejects an external move),
  `../specs/draft-schedule.schema.md` and axiom 05 (the hard overlap rule is
  scoped to the in-app drag tier).
- This narrows the overlap rule to the tiers where the system can still act on
  it (auto-placement and pre-approval adjustment); it does not remove it.

## Alternatives Considered

- **Adopt only block-vs-block overlap; keep busy-event overlap rejecting.**
  The same dead-end survives for the most common overlap (the user's own
  meetings), which the user can see perfectly well on the surface they edited.
  Rejected.
- **Make overlap advisory for in-app drag too.** Not needed to fix the
  reported dead-end, and it would remove a cheap, honest refusal on a surface
  where the system can still offer a clean slot before anything exists on the
  calendar. Deferred until dogfooding shows that wall.
- **Auto-replan around the overlap.** Autonomous replanning is forbidden in
  the MVP (axiom 00 / AGENTS.md); every plan mutation goes through review.
  Rejected.
- **Also demote allowed-hours / daily-load for external moves.** Those are
  user-stated policy bounds, not placement preferences; silently accepting a
  move that breaks them would erode the meaning of the user's own settings.
  Kept as rejections; revisit only with explicit product direction.

## Related Docs

- `ADR-0008-advisory-manual-ordering.md` (the advisory-tier pattern this extends)
- `../axioms/05-scheduler-policy.md` (drag-to-adjust: hard vs advisory)
- `../axioms/06-calendar-safety.md` (in-app source-of-truth; opt-in inbound sync)
- `../specs/calendar-reconciliation.schema.md`
- `../specs/draft-schedule.schema.md` (server-side re-validation)
