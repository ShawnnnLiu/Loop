# 01 · Loop Engineering — Close the Loops the User Can Feel

Priority: **highest in this pass.** Every item here is a place where the
system already collects a signal or holds a capability, but the user either
gets stranded, misinformed, or asked a question they cannot answer. These are
trust-breaking failures; no prompt quality compensates for them.

What already works (do not disturb): the supervisor is a single pure
transition dict (`backend/src/agentic_calendar/supervisor/transitions.py:17-101`),
both inner loops are provably bounded
(`contracts/validation_result.py:25`, `app/cycle.py:140`), disposition memory
is a fully closed feedback edge (`app/cycle.py:569-580` → scheduler filter
`:753`, planner exclusion `:415,514`), and drift → recalibration → approval is
a genuine closed loop for duration drift (`app/cycle.py:1623-1651`,
`_recalibrated_plan` `:523-567`). The proposals below add missing edges; none
weaken an approval gate.

---

## 1. Write-failure recovery from the SPA (the standing dead-end)

**Problem (user experience).** If a calendar write fails or verification
fails, the run lands in `CALENDAR_WRITE_FAILED_STATE` and the user is stuck
forever: the state's only outbound edge requires `CALENDAR_ROLLBACK_*`
signals that **no route or service ever emits**
(`supervisor/transitions.py:69-70`; grep confirms no emitter in
`app/`). There is no `/rollback` or `/reconcile-after-crash` endpoint in
`app/web/routes_cycle.py`. Orphaned, unverified events sit on the user's real
calendar. The SPA's only affordances are escape-by-abandon
(`frontend/src/screens/Approval.tsx:159-174` "Back to the draft";
`frontend/src/lib/review.ts:26-27` "Build a new plan →"). Recovery exists but
is operator-CLI-only (`tools/rollback_calendar.py:108`,
`calendar_writer/manager.py:490-608` `reconcile_after_crash`).

Worse, the frontend lies about it: `Approval.tsx:62-63` carries an inline
comment claiming "the engine has already rolled back any unverified events,"
which contradicts both its own header (`Approval.tsx:17-20`) and the backend
(`manager.py:207-211` — "No auto-retry"; `_verify_and_finalize`
`manager.py:819-843` marks mappings `VERIFICATION_FAILED` and raises,
invoking no rollback).

**Proposal.**
- Add a service method + route pair exposing the two recovery primitives that
  already exist on `CalendarWriteManager`:
  - `POST /api/rollback` → `manager.rollback_run(...)`
    (`calendar_writer/rollback.py:36-77`, id-based deletes, per-event failure
    recording), then emit the already-defined `CALENDAR_ROLLBACK_COMPLETED` /
    `CALENDAR_ROLLBACK_FAILED` signals so the run reaches
    `ERROR_REQUIRES_USER` cleanly instead of rotting.
  - `POST /api/reconcile-after-crash` → `manager.reconcile_after_crash(...)`
    (`manager.py:490-608`) for the retry-missing-events path. Note it already
    re-runs the `approved_payload_hash` recheck (`manager.py:511-517`), so the
    axiom-06 gate is preserved by construction.
- SPA: replace the abandon-only UI on write/verify failure with two explicit,
  honest choices — "Remove the events that were written" (rollback) and
  "Retry the missing events" (crash reconcile) — plus the existing "Build a
  new plan" as the third option.
- Fix the false comment at `Approval.tsx:62-63` regardless of everything
  else (one-line honesty fix; the audit memory already flagged this class of
  copy as a HIGH finding once before).

**Why.** This is the most severe smoothness/reliability failure in the
product: a partial write is exactly the moment the user most needs the tool to
be trustworthy, and today it shrugs. Both primitives are already implemented,
tested, and hash-gated; the work is a route, two signals, and honest UI copy.

**Touchpoints.** `app/cycle.py` (new service methods near `write()`
`:1406-1543`), `app/web/routes_cycle.py`, `supervisor/transitions.py:69-70`
(possibly one new edge for the retry path), `calendar_writer/manager.py`
(no logic change expected), `frontend/src/screens/Approval.tsx`,
`frontend/src/lib/review.ts`, `frontend/src/lib/approval.ts`.

**Axiom/spec implications.** None violated — rollback/reconcile keep the
approval + hash gates. New typed transitions must be added to the transition
table with tests (valid + invalid), per the testing requirements in
`CLAUDE.md`. Calendar-write specs in `docs/specs/` should gain the new
routes' contracts.

**Open questions.** Should rollback require a fresh confirmation click with
the event count shown ("Remove 14 events written on …")? (Recommended: yes —
it is a destructive external action.)

---

## 2. Surface `REPLAN_REQUIRED` — stop telling drifting users everything is fine

**Problem (user experience).** The backend closes the drift→replan loop
(`app/cycle.py:1644-1651` parks the run in `REPLAN_REQUIRED`;
`_propose_replan` `:437-475` continues it), but the SPA never tells the user:
`frontend/src/lib/review.ts:19-31` maps any unrecognized run state — including
`replan_required` — to `'written'`, so the Week screen renders **"Your week is
scheduled"** to a user whose plan has measurably drifted. Additionally, the
`ask_each_time` recovery mode has no picker UI, so a replan pending a user
choice just 409s on `/propose` (`app/cycle.py:456-460`, `pending_user_choice`
`:1846`).

**Proposal.**
- Add an explicit `replan_required` review mode in `review.ts` with its own
  banner: what drifted (typed drift type + the reflection prose that is
  already generated at `app/cycle.py:1626-1634`), and a single CTA that calls
  `/propose` to run the replan.
- Build the recovery-mode picker for `ask_each_time`: when `/propose` returns
  the pending-choice state, render the deterministic mode options
  (`DRIFT_ACTION_TO_RECOVERY_MODE`, `app/cycle.py:158-170`) as cards with
  plain-language descriptions, then re-call `/propose` with the chosen mode.
- Today screen: a small "your plan needs attention" chip when the active run
  is parked, so the signal is visible where the user actually lives.

**Why.** This is the flagship loop of the whole product — telemetry in,
adapted plan out — and it is finished on the backend but invisible. "The
system noticed I'm behind and proposed a fix" is precisely the "actual good
guidance" experience this version is about. Right now the user must guess to
press the replan button.

**Touchpoints.** `frontend/src/lib/review.ts:19-31`,
`frontend/src/screens/ScheduleReview.tsx`, `frontend/src/screens/Today.tsx`,
possibly a small read-projection addition in `app/cycle.py` (`draft_view`
`:1950-1979`) to expose the parked state + drift summary;
`app/web/routes_cycle.py` for the mode-choice parameter (already accepted by
`propose`).

**Axiom/spec implications.** None — the replan still flows through
validation → scheduler → approval (`recovery.py`, `replan.py`). Pure
surfacing.

**Open questions.** Should reflection prose appear in the banner (friendly)
or behind a "why?" disclosure (quieter)? Recommended: one-line summary +
disclosure.

---

## 3. Wire reconciliation and the starved drift rules into the classifier

**Problem (user experience).** Two documented feedback edges are dead:

- *Reconcile → drift:* `reconcile()`'s docstring says deletions/rejections are
  "left for the drift loop" (`app/cycle.py:1068-1070`), but the classifier's
  `external_conflict_task_ids` input is never populated from reconciliation —
  `EVENT_DELETED` dispositions feed only read projections
  (`app/cycle.py:640-655`). An external delete shows a banner and stops.
- *Starved rules:* `ingest` constructs `DriftInput(plan=plan, events=events)`
  only (`app/cycle.py:1624`), so four of nine deterministic drift rules can
  never fire in production — `capacity_mismatch`, `calendar_fragmentation`,
  `accountability_mismatch`, `sponsor_pressure_mismatch`
  (`drift/classifier.py:209-240, 383-485`); only the debug CLI
  (`tools/classify_drift.py`) supplies the optional inputs.

**Proposal.**
- Populate `external_conflict_task_ids` from the reconcile outcome (rejected
  adoptions + `EVENT_DELETED` dispositions) when `ingest` next runs, so an
  external conflict can drift-route to `external_conflict` and reach the
  replan decision (`_replan_decision` `app/cycle.py:1818-1876`) instead of
  dead-ending in a banner.
- Compute and pass the missing `DriftInput` fields in `ingest`:
  `weekly_cycles` and `fragmentation` are derivable from the stored draft +
  telemetry; `declined_interventions` exists conceptually in accountability
  but is never computed (see §4). Do them in that order — capacity and
  fragmentation are the two with direct scheduling consequences the user
  feels.

**Why.** "Smooth" includes *the calendar staying truthful without the user
babysitting it*. A user deleting a study block in Google Calendar is the
loudest feedback they will ever give; today the system records it, displays
it, and does nothing. Routing it into the same drift→replan loop as duration
drift makes external edits first-class feedback.

**Touchpoints.** `app/cycle.py` (`ingest` `:1605-1651`, `_event_deleted_ids`
`:640-655`, reconcile outcome plumbing `:1051-1304`),
`drift/classifier.py:121-143` (no rule changes — just feed the inputs),
`drift/policy.py:19-46`, tests under `tests/drift/` and golden scenarios.

**Axiom/spec implications.** Axiom 07 (deterministic drift) is upheld — the
classifier stays deterministic; we only feed it. The EVENT_DELETED axiom-06
stance ("surfacing-only, never completion/drop") is preserved: routing to
drift is surfacing + replan proposal, not a silent mutation.

**Open questions.** Should an external delete alone be enough to *require* a
replan, or only *recommend* one? Recommended: recommend (park nothing;
banner + drift feed), since delete intent is ambiguous.

---

## 4. Make accountability answerable: recommitment + weekly check-in

**Problem (user experience).** The accountability loop asks and never
listens:

- `request_recommitment` is called when a nudge fires
  (`app/cycle.py:1714-1722`), but the answer path `record_recommitment`
  (`accountability/recommitment.py:157-175`) has **zero production callers**,
  and nothing reads `RecommitmentEvent` to drive behavior — the mapping
  `RECOMMITMENT_CHOICE_TO_RECOVERY_MODE` (`recommitment.py:40-47`) is never
  exercised. The user is asked to recommit and literally cannot respond.
- `CheckinEvent` is never constructible from the product:
  `checkin_store.append` has no production caller, so
  `evaluate_checkin` always sees an empty history and the policy engine emits
  `CHECKIN_DUE` / `CHECKIN_MISSED` forever (`accountability/policy_engine.py:140-169`).
  (The Today `/checkin` at `app/cycle.py:2097-2132` is per-task completion
  telemetry — a different object.)

**Proposal.**
- `POST /api/recommit` → `record_recommitment`, and have the recorded choice
  feed `_replan_decision` via the existing choice→recovery-mode mapping, so
  "recommit: reduce load" actually produces the reduced-load replan draft.
- A lightweight weekly check-in surface (one card on Today or Accountability:
  "How did this week go?") that appends a real `CheckinEvent`, clearing
  `CHECKIN_DUE`.
- Until both exist, consider suppressing the unanswerable nudges — a system
  that visibly asks for input it cannot receive reads as broken.

**Why.** "Friendly" fails hardest when the product makes a social gesture and
then ignores the reply. These are the two clearest cases in the codebase of
UI-visible promises with no fulfillment path. Both stores, contracts, and
policy consumers already exist; the missing piece is one route + one screen
element each.

**Touchpoints.** `app/web/routes_cycle.py`, `app/cycle.py`
(`_evaluate_accountability` `:1674-1725`, `_replan_decision` `:1818-1876`),
`accountability/recommitment.py`, `accountability/policy_engine.py:140-169`,
`frontend/src/screens/Today.tsx`, `frontend/src/screens/Accountability.tsx`.

**Axiom/spec implications.** The policy engine stays deterministic; the
recommitment choice is typed, not prose. Check `docs/specs/` for the
recommitment/check-in contracts before adding routes (spec-first rule).

**Open questions.** Whether Phase 6d threshold adaptation
(`accountability/adaptation.py:67`, also caller-less) should ride along here
or stay deferred; recommended: defer, it needs `declined_interventions`
plumbing first (§3).

---

## 5. A general "resume" affordance for `ERROR_REQUIRES_USER`

**Problem (user experience).** `ERROR_REQUIRES_USER` is a terminal sink by
design (`supervisor/transitions.py:95-100` routes every panic there), and the
only recourse anywhere is starting a brand-new run (`propose` mints a fresh
`INITIAL` run, `app/cycle.py:365-372`). Repair exhaustion, capacity
exhaustion, LLM panic, and (post-§1) rollback completion all funnel to the
same "start over" experience, discarding the user's context about *why*.

**Proposal (lighter-touch than a state-machine change).** Keep the sink
semantics, but make the fresh-`propose` path *reason-aware*: when the prior
run ended in `ERROR_REQUIRES_USER`, surface the typed `reason_code` and the
`UserFacingExplanation` (already generated at `app/cycle.py:406-408, 727-729`)
on the Generation screen, and pre-seed the retry appropriately (e.g. capacity
failures pre-open the constraints step of onboarding; repair exhaustion offers
"try again" which is honest, since LLM retries are stochastic).

**Why.** "Reliable" is partly *perceived* recovery: even when the answer is
"try again," a system that says *what happened and what to change* feels
sturdy; one that silently resets feels flaky. This costs a read-projection
and SPA copy, no supervisor change.

**Touchpoints.** `app/cycle.py` (read projection near `draft_view`
`:1950-1979`), `frontend/src/screens/Generation.tsx`,
`frontend/src/screens/Onboarding.tsx` (deep-link to constraints step).

**Axiom/spec implications.** None; no transition changes.

---

## Explicitly deferred (noted so they aren't re-litigated)

- **Phase 6c/6d activation** — `evaluate_power_user_eligibility`
  (`duration_estimation/power_user.py`) and the `refinement` parameter of
  `resolve_effective_multipliers` (`duration_estimation/pooled.py:320, 436`)
  remain caller-less; pooled serving stays structurally inert
  (`app/cycle.py:558`, `model=None`). Personalization depth is not a UX
  bottleneck yet; the per-user calibration path already works.
- **Advisory-by-design drift types** (`topic_avoidance`, `low_engagement` →
  `None` in `DRIFT_ACTION_TO_RECOVERY_MODE`, `app/cycle.py:158-170`) — after
  §2 lands, their reflection prose at least becomes visible; converting them
  to actionable prompts is a later product decision.
