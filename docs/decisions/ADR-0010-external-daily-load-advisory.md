# ADR-0010: External Calendar Moves May Exceed the Daily Load Cap (Advisory, Not a Rejection)

## Status

Accepted

## Context

ADR-0009 made overlap advisory for inbound reconciliation and deliberately kept
the two remaining hard rules — allowed hours/weekend and daily load — as
rejections, noting the daily-load demotion should be revisited "only with
explicit product direction." Dogfooding then reproduced the same dead-end shape
for daily load that ADR-0009 fixed for overlap: the user dragged a Loop event on
their own Google Calendar onto a day that was already at their
`max_daily_study_min`. Reconcile rejected the move ("that day would go over
your daily study limit") and the only exit offered was a full replan. But the
edit **already happened** on the user's own calendar: reconciliation is
read-only, so rejecting it undoes nothing — it just leaves the plan out of sync
with the calendar the user just edited, and demands a rebuild to converge.

Worse, adoption is all-or-nothing across a pull: one over-cap day blocks every
other (perfectly valid) move detected in the same pull.

The product direction is now explicit: the Planner and Scheduler must never
*plan* beyond the user's daily/weekly study-hour limits, but a user who moves
their own tasks on their own calendar gets headroom — we respect their choice
and warn, rather than refusing an accomplished fact.

## Decision

Daily load becomes **advisory** for external reconciliation moves. Deterministic
auto-placement and in-app drag-to-adjust keep the hard
`DAILY_LOAD_EXCEEDED` rule. Both stay deterministic.

1. **Reconciliation adopts over-cap moves.** The shared placement validator
   (`scheduler/adjustment.py`, `validate_placements`) gains a keyword-only
   `daily_load_advisory` mode, used **only** by the reconciliation path
   (alongside ADR-0009's `overlap_advisory`). In that mode a calendar day whose
   total exceeds `max_daily_study_min` emits a non-blocking
   `DAILY_LOAD_ADVISORY` warning instead of a hard `DAILY_LOAD_EXCEEDED`
   conflict.
2. **Every task on the over-cap day warns.** Only moved tasks produce deltas,
   so the advisory must land on whichever block the user actually moved — the
   same both-sides pattern ADR-0009 uses for block-vs-block overlap. Warnings
   on unmoved tasks simply never surface (they attach to no delta).
3. **The adopted delta carries the heads-up.** An adopted move/resize may now
   carry `DAILY_LOAD_ADVISORY` as its `reason_code`. Precedence when several
   advisories apply: `DAILY_LOAD_ADVISORY` > `DEPENDENCY_ADVISORY` >
   `OVERLAP_ADVISORY`. The daily cap is a bound the user explicitly configured
   and its breach is invisible on the grid; an overlap is visible on the grid
   itself (ADR-0009's existing tie-break stays below it).
4. **Planner, Scheduler, and in-app drag are unchanged.** Auto-placement never
   plans past `max_daily_study_min` (or the weekly capacity bound), and an
   in-app drag that pushes a day over the cap is still refused with
   `DAILY_LOAD_EXCEEDED` — pre-approval, nothing exists on the calendar yet and
   a clean slot can still be chosen cheaply.
5. **Rejection now means allowed-hours only.** On the reconcile path a
   `rejected` delta now only ever carries `OUTSIDE_ALLOWED_HOURS`.
   `DAILY_LOAD_EXCEEDED` remains in the contract's rejected-delta vocabulary
   (`ADJUSTMENT_REASON_CODES`) — it is still the in-app drag refusal code and
   historical reconciliation results carry it — but the reconcile producer no
   longer emits it.
6. **Not an external conflict.** An adopted-with-`DAILY_LOAD_ADVISORY` delta is
   the user's own placement: like `DEPENDENCY_ADVISORY` (ADR-0008) and
   `OVERLAP_ADVISORY` (ADR-0009) it never feeds the drift classifier's
   `external_conflict_task_ids` input and emits no `DRIFT_EXTERNAL_CONFLICT`.

## Consequences

- The reported dead-end is gone: a calendar-side move onto an already-full day
  is adopted with a heads-up, the plan converges to the calendar, and no
  rebuild is demanded — and it no longer blocks unrelated moves in the same
  pull.
- `DAILY_LOAD_ADVISORY` is a new **non-blocking** `reason_code`. Clients must
  treat it on an `adopted` delta as informational.
- The internal draft may now legitimately total more than
  `max_daily_study_min` on a day the user stacked themselves. The daily cap
  stays authoritative everywhere the system chooses placements; it is only the
  user's own external placement that may exceed it.
- Allowed hours/weekend (`OUTSIDE_ALLOWED_HOURS`) is now the only reconcile
  rejection. It remains a rejection deliberately: it bounds *when the user is
  willing to be scheduled at all*, and demoting it was not part of the stated
  product direction. Revisit separately if dogfooding hits that wall.
- The weekly capacity bound needs no counterpart change: reconciliation never
  re-checks weekly capacity (a move within or across weeks changes no
  durations), so only planning paths enforce it — and those are unchanged.
- Specs updated: `../specs/calendar-reconciliation.schema.md` (adopted may
  carry `DAILY_LOAD_ADVISORY`; daily load no longer rejects an external move),
  `../specs/draft-schedule.schema.md` and axiom 05 (the hard daily-load rule is
  scoped to the tiers where the system chooses placements).

## Alternatives Considered

- **Keep rejecting and improve the error copy.** The copy was already honest;
  the dead-end is structural — reconciliation cannot undo an edit it only
  reads. Rejected.
- **Also demote allowed-hours/weekend.** Not asked for, and it is a different
  kind of bound (when the user may be scheduled at all, not how much). Kept as
  the sole rejection; revisit only with explicit product direction. Same
  posture ADR-0009 took toward this decision.
- **Reuse `DAILY_LOAD_EXCEEDED` on adopted deltas.** Overloading one code with
  both a hard refusal and a non-blocking heads-up would make clients infer
  severity from the disposition. A distinct `*_ADVISORY` code keeps severity in
  the code itself, matching `OVERLAP_ADVISORY`. Rejected.
- **Auto-replan around the over-cap day.** Autonomous replanning is forbidden
  in the MVP (axiom 00 / AGENTS.md); every plan mutation goes through review.
  Rejected.

## Related Docs

- `ADR-0009-authoritative-external-overlap.md` (the advisory demotion this extends)
- `ADR-0008-advisory-manual-ordering.md` (the advisory-tier pattern)
- `../axioms/05-scheduler-policy.md` (hard vs advisory tiers)
- `../specs/calendar-reconciliation.schema.md`
- `../specs/draft-schedule.schema.md` (server-side re-validation)
