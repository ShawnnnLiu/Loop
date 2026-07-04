# ADR-0008: Advisory Manual Ordering (Completion-Relative, Non-Blocking)

## Status

Accepted

## Context

Two axioms made dependency ordering a hard wall everywhere:

- Axiom 11 (prerequisite logic): prerequisites are a deterministic function of
  dependencies **and completion state**; a task with unmet prerequisites is not
  scheduled before its blockers.
- Axiom 05 (scheduler policy): the drag-to-adjust placement validator refused a
  manual move that "starts before a prerequisite ends" with `DEPENDENCY_BLOCKED`.

But the drag-to-adjust validator (`scheduler/adjustment.py`, step 5) enforced
ordering against each task's **raw** `dependencies`, ignoring completion — so it
diverged from axiom 11's own definition *and* from the scheduler's
completion-aware filter (`scheduler/greedy.py`). In dogfooding, a user who had
completed (and dropped) the earlier tasks of a chain was then refused when
dragging a later task earlier:
`DEPENDENCY_BLOCKED: t21 starts before prerequisite t20 ends` — even though t20
was already done and gone. The hard wall blocked a legitimate user override.

Constraints that shape the fix:

- The deterministic greedy scheduler's auto-placement produces good,
  topologically-ordered defaults; relaxing **it** would degrade first-draft
  quality (axiom 05 quality metrics). That tier must stay hard.
- A manual move is an explicit user override of *placement*. The system already
  relaxes soft preferences (deep-work windows, `min_break_between_deep_blocks_min`)
  for manual moves for exactly this reason.
- Completion/drop state must be available to the validator for the check to be
  completion-relative. It is supplied by the new disposition projection
  (`../specs/task-disposition.schema.md`), unioned across plan versions.

## Decision

Dependency ordering on a **manual placement override** becomes
**completion-relative AND advisory**. Deterministic auto-placement stays **hard**.

1. **Two tiers, both deterministic.**
   - *Auto-placement (greedy scheduler)* — unchanged. A task with unmet
     prerequisites is not auto-scheduled before its blockers; the scheduler emits
     `DEPENDENCY_BLOCKED` if asked. Topological ordering remains the default.
   - *Manual override (drag-to-adjust, or an adopted external-calendar move)* —
     advisory. The validator no longer refuses a move that starts before a
     prerequisite ends. It emits a non-blocking `DEPENDENCY_ADVISORY` warning and
     the move is applied.
2. **Completion-relative.** The advisory check skips any prerequisite in the
   user's completed/dropped set. A completed or dropped prerequisite produces no
   warning at all; only an **unfinished** prerequisite the move now precedes
   produces `DEPENDENCY_ADVISORY`.
3. **Still deterministic; the LLM is untouched.** The advisory decision is a pure
   function of (dependencies, completion/drop set, placement times). No LLM marks
   prerequisites met — axiom 11's "Forbidden" clause and the `prerequisites_met`
   computation are unchanged. An LLM may only phrase the heads-up.
4. **Hard rules are unchanged.** Overlap (`NO_VALID_CONTIGUOUS_BLOCK`),
   allowed-hours/weekend (`OUTSIDE_ALLOWED_HOURS`), and daily-load
   (`DAILY_LOAD_EXCEEDED`) still refuse a manual move. A move may be **both**
   refused (a hard conflict) and warned (an advisory) at once; a hard conflict
   still blocks.
5. **Write-path safety is unchanged.** The advisory rides in the adjust result's
   `warnings`, never as a refusal; the approved draft's hash recheck (axiom 06) is
   unchanged. Advisory ordering never authorizes or suppresses a calendar write.
6. **Reconciliation.** An adopted external move/resize that now precedes an
   unfinished prerequisite is still **adopted** and carries `DEPENDENCY_ADVISORY`
   as its only non-null `reason_code`. Prerequisite ordering can no longer
   **reject** a reconciliation delta; rejection stays reserved for the hard
   placement codes. An adopted-with-advisory delta is **not** an external conflict
   and does not feed the drift `external_conflict_task_ids` input.

## Consequences

- The reported dead-end (a refused drag past an already-completed prerequisite)
  is gone; the user gets a heads-up instead of a wall.
- `DEPENDENCY_ADVISORY` is a new **non-blocking** `reason_code`. Clients must treat
  a populated `warnings[]` on an `applied: true` adjust result as informational,
  not as failure.
- The drag-to-adjust validator gains a completed/dropped-id parameter. If the
  disposition projection is empty (e.g. the validator change ships before the
  projection is wired), it degrades **safely** to "warn on every unfinished
  prerequisite" — never to a block.
- Specs updated: `../specs/draft-schedule.schema.md` (server-side re-validation
  splits hard vs advisory) and `../specs/calendar-reconciliation.schema.md`
  (adopted may carry `DEPENDENCY_ADVISORY`; ordering no longer rejects). Axioms 05
  and 11 amended.
- This **narrows** a non-negotiable hard rule to the auto-placement tier rather
  than removing it. Determinism, the dependency contract, and the
  `prerequisites_met`-forbidden invariant are all preserved.

## Alternatives Considered

- **Completion-relative only (still hard).** Make the manual-move check skip
  completed/dropped prerequisites but still *refuse* on an unfinished one. Fixes
  the reported case (that prerequisite was completed) but still walls a deliberate
  override past a genuinely-unfinished prerequisite — and a manual move is an
  explicit override. Rejected: keeps a wall where the product wants a heads-up.
- **Override flag (hard by default, per-move opt-out).** Keep the refusal but let
  the client resend with `force=true`. Rejected: adds control-plane state to a
  placement request, doubles the round-trip, and pushes a safety judgment to the
  client for something that is not a safety rule (ordering ≠ overlap/hours/load).
- **Relax the scheduler too.** Make deterministic auto-placement advisory as well.
  Rejected: it would degrade first-draft schedule quality; the greedy topological
  default is a feature, not a constraint to relax.

## Related Docs

- `../axioms/05-scheduler-policy.md` (drag-to-adjust: hard vs advisory)
- `../axioms/11-prerequisite-logic.md` (completion-relative prerequisites)
- `../axioms/15-plan-versioning-and-diffs.md`
- `../specs/draft-schedule.schema.md` (server-side re-validation)
- `../specs/calendar-reconciliation.schema.md` (adopted advisory; ordering no longer rejects)
- `../specs/task-disposition.schema.md` (completed/dropped projection)
- `ADR-0002-preview-only-calendar-writes.md`
