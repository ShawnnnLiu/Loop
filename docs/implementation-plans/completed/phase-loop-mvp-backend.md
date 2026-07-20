# Phase: Loop MVP — Backend For The Hi-Fi Frontend

Status: **complete** — implemented and merged to `main`.

Backend work required so the hi-fi **Loop** design (`docs/design-reference/design-loop/`)
can run against the real engine. Loop is the interview-prep / productivity
product; this phase wires the few backend gaps the `design-loop/` screens need
and explicitly scopes out everything else the design folder shows.

## Status

Planned, not started. Scoped from a design-vs-backend audit (2026-06-18). The
audit's headline: most `design-loop/` screens are already backed by existing
deterministic + LLM machinery and only need frontend wiring — the genuinely
missing backend is small. This document records the product decisions that set
that scope and plans the one substantive build (drag-to-adjust) plus the two
thin changes (résumé capture, horizon confirmation).

## Decisions (authoritative for this phase)

These were made explicitly by the product owner on 2026-06-18. They govern scope;
anything conflicting with them is out of scope for this phase.

- **D-1 · Product = Loop.** The MVP is **Loop**, the interview-prep / job-search
  scheduler (`design-loop/`). The college-admissions material in the design
  folder (`claude_code_handoff/`, Maya Chen, transcript→GPA parse, current-term
  courses, essay/supplement milestones, ED/EA/RD decision plans) is **ignored
  for this phase**.
- **D-2 · Framing = productivity, for beta.** Beta ships with productivity
  framing. **Admissions framing comes later** as a separate product track; do
  not build admissions-specific contracts or surfaces now.
- **D-3 · Résumé = store + pass, do NOT parse yet.** No résumé-parser LLM node
  in this MVP. Capture the résumé as **raw text on the user profile** and pass
  it through to the **Strategist** as additional context. The future
  extract→review→confirm parser node is **documented as deferred** (see
  "Deferred / Future Work") because adding an LLM node class is an architecture
  change (axiom 01 allows only Strategist / Planner / ReflectionSummary /
  UserFacingExplanation) and needs its own approval.
- **D-4 · No 60-second undo window.** The calendar-write rollback primitive
  (`calendar_event_mapping`) already exists; the time-bounded undo deadline +
  finalize sweep + undo endpoint are **not** built in this MVP.
- **D-5 · No motivation-profile capture.** Onboarding still omits the motivation
  profile; the Accountability dashboard stays empty-state-first. Unchanged from
  the deferral already tracked in `phase-frontend-mvp.md`.
- **D-6 · Drag-to-adjust schedule review IS in scope.** The frontend
  (`design-loop/schedule.jsx`) is ready; this phase adds the **backend routing**
  to persist user adjustments to a proposed draft. It **must support moving a
  block across days**, not only changing the time within the same day. The
  server **re-validates every adjustment and never trusts the client's
  conflict-checking.**
- **D-7 · Approval is plan-level.** The whole draft is approved and written as a
  single unit (no per-block accept/done). This is acceptable precisely because
  drag-to-adjust (D-6) gives the user per-block control *before* the single
  approval.
- **D-8 · Write the entire horizon; no per-week approval.** Approve/write covers
  the full plan horizon at once. This is already the engine's default
  (`propose` uses `horizon_days = timeline_weeks * 7` and the scheduler places
  the whole plan); this phase confirms and locks that behavior, it does not add
  per-week slicing.
- **D-9 · "Why this block" reuses UserFacingExplanation.** No new per-block
  reasoning LLM node. Any explanation surface reuses the existing deterministic
  `UserFacingExplanationNode`.
- **D-10 · No agent dock.** No conversational thread / tool-call log / slash
  commands (`/recover`, `/why`, `/regen week`, `/mock`) in this product.
- **D-11 · No permission / mentor gate.** No sponsor/peer sharing or per-field
  consent surface now (the `consent/` primitives stay as-is, unused by UI).

## Required Docs

Read before implementing the relevant deliverable:

- `../../../AGENTS.md`
- `../../axioms/01-system-boundaries.md` (LLM node classes — D-3 boundary)
- `../../axioms/02-state-machine.md` (where adjust sits in the run lifecycle)
- `../../axioms/03-data-contracts.md` (new `resume_text`; adjustment request)
- `../../axioms/04-validation-layer.md` (re-validating an adjusted draft)
- `../../axioms/05-scheduler-policy.md` (manual override vs scheduler placement)
- `../../axioms/06-calendar-safety.md` (payload hash + approval after adjust)
- `../../specs/user-profile.schema.md`
- `../../specs/strategist-input.schema.md`
- `../../specs/draft-schedule.schema.md`
- `../../specs/scheduler-output.schema.md`
- `../../specs/validation-result.schema.md`
- `../../design-reference/design-loop/schedule.jsx` (the drag UI this routes)
- `../../design-reference/design-loop/onboarding.jsx` (résumé step, the one AI step)

## Deliverables

### D-A · Résumé capture → Strategist (implements D-3)

The smallest change: a raw résumé string on the profile that reaches the
Strategist. No parsing, no new node, no file storage.

1. **Spec first.** Update `../../specs/user-profile.schema.md`: add optional
   `resume_text: str | None` (free text the user pastes; PII, user-scoped, never
   used for training; absent for users who skip the step). Note it is *unparsed*
   context for the Strategist, not a structured field.
2. **Contract.** Add `resume_text: str | None = None` to
   `contracts/user_profile.py::UserProfile`. Optional with a `None` default so
   every existing fixture and test stays valid.
3. **Strategist input.** No code change needed — `StrategistInput` already
   bundles `user_profile`, so `resume_text` reaches the node automatically.
   Confirm the **real Anthropic Strategist adapter** includes `resume_text` in
   its prompt context when present (and omits it cleanly when `None`). The
   deterministic fixture strategist keys off `target_role` only and is
   unaffected.
4. **Onboarding surface.** Add a "Paste your résumé (optional)" `<textarea>` to
   the onboarding form (`app/web/templates/onboard.html` + `pages.py`
   `_build_profile` / `_values_from_record` / `_SCALAR_FIELDS`). Mirror the
   design's privacy line ("stays on your account, never used for training").
   Round-trips through the same `UserProfile` validation as every other field.
5. **Privacy.** `resume_text` is stored only on the user's own profile record;
   it is not shared cross-user and is deleted with the profile. No training use.

### D-B · Drag-to-adjust schedule review (implements D-6; the substantive build)

A new route that takes the user's adjusted block positions for a *proposed*
draft, re-validates them server-side, and replaces the pending draft (with a
fresh canonical hash) so the existing approve→write flow writes the adjusted
schedule. Plan-level (D-7); entire horizon (D-8).

1. **Spec first.** Update `../../specs/draft-schedule.schema.md` to describe an
   *adjusted* draft: same `plan_version`, new `draft_schedule_id`, **entry order
   preserved** (only moved tasks change time), duration preserved per task. Add
   the adjustment-request shape (a list of `{task_id, start}` overrides).
   `DraftSchedule.with_adjustments(...)` (a pure contract method) does the
   structural apply.
2. **Request model.** `DraftAdjustment` lives in `scheduler/adjustment.py`
   (alongside the placement validator), mirroring how `FreeBusyInterval` lives in
   `scheduler/inputs.py` — a deterministic request input, not a registered/hashed
   contract, so no generated JSON schema. It carries `task_id` + new tz-aware
   `start` only. **End is derived server-side** as
   `start + (original.end − original.start)` so the client cannot resize a block
   — only move it. Unknown or duplicate `task_id`s are rejected.
3. **Cross-day support (D-6).** Entries are full datetimes, so a cross-day move
   is just a new date component in `start`. The route must accept any tz-aware
   `start` within the plan horizon — explicitly remove any "same-day only"
   assumption. Validation (below) handles the destination day's constraints.
4. **Service method.** `CycleService.adjust(user_id, adjustments, run_id=None)`:
   - Load the run's current **proposed** draft. Allowed **only before
     approval** — adjusting an already-approved run is refused with a typed
     reason (re-approval is the contract, not silent mutation; consistent with
     axiom 06's stale-approval guarantee).
   - Apply overrides to a working copy of the entries; untouched tasks keep
     their positions.
   - **Re-validate deterministically, reusing the existing validators — never
     trust the client's snap-back:**
     - no overlap with locked/busy windows (use the free/busy captured at
       propose time; do not trust the client);
     - no overlap between draft entries;
     - hard constraints: `no_events_before` / `no_events_after`,
       `max_daily_study_min` per day, `allow_weekends` (a move onto a disallowed
       weekend is rejected);
     - prerequisite ordering still holds — a move that puts a task before a
       prerequisite ends is rejected;
     - **Soft placement is relaxed for manual moves** — both deep-work-window
       adherence *and* `min_break_between_deep_blocks_min`. The user is
       explicitly overriding placement, and the design grid (08:00–22:00) is
       broader than the deep-work windows; re-imposing these would reject
       legitimate moves. Documented in `05-scheduler-policy`: manual adjustments
       are bound by hard day/time/load bounds, no-overlap, and prerequisite
       order, but not by the soft placement the greedy scheduler optimizes for.
       (Horizon bounds are not separately enforced — the moved entries stay
       tz-aware datetimes and the whole adjusted draft is what gets approved and
       written.)
   - Every rejection returns a typed `reason_code` (reuse existing scheduling /
     user-fit codes; do not invent opaque errors).
   - On success: build a **new immutable `DraftSchedule`** (new
     `draft_schedule_id`, same `plan_version`, entry order preserved), persist
     it, point the run at it, and return it with its recomputed
     `canonical_payload_hash`.
5. **Route.** `POST /api/adjust` (JSON, mirrors the other cycle routes; acting
   user from the session, never the body). Free/busy is fetched **server-side**
   via the shared `best_effort_free_busy` helper (auth-gated; dev mode falls back
   to no calendar awareness), so re-validation never trusts a client-supplied
   busy list. No `/ui/adjust` form is added — the shipped Jinja surface has no
   drag screen, and the ready hi-fi frontend calls the JSON API.
6. **Approval/write unchanged.** `approve` records the hash of the (adjusted)
   stored draft; `write` rechecks it. Axiom 06 safety is preserved end-to-end —
   no new bypass.
7. **State machine.** Adjust replaces the pending draft within the
   proposed/awaiting-approval state. Decide during implementation whether this
   is a self-loop signal (`DRAFT_ADJUSTED`) or a pure artifact swap with no
   lifecycle transition; either way it must not skip the approval gate. Flag
   axiom 02 if a new signal is added.

### D-C · Confirm full-horizon, plan-level write (implements D-7, D-8) — ✅ DONE

No new logic — a guard-and-document task. Confirmed:

1. `propose` defaults to the full timeline horizon and the scheduler places the
   whole plan: `propose` sets `horizon_days = timeline_weeks * 7` when no
   explicit horizon is given (`app/cycle.py`), and the docstring records that the
   Phase 1 scheduler places the WHOLE plan inside the horizon.
2. `approve`/`write` operate on the whole draft as one unit — there is no
   per-week or per-block slicing in the approve/write path.
3. Locked in by `tests/app/test_cycle.py::
   test_multi_week_plan_writes_full_horizon_in_single_approval`: a profile with
   one Monday deep-work window + a 120-min daily cap forces the dependent task
   into the following week (draft spans ≥2 ISO weeks), and a single
   approve → write writes/verifies **every** entry — guarding against a future
   regression toward per-week slicing.

**Per-week / selective-week approval is intentionally not offered** (D-8);
drag-to-adjust (D-B) gives per-block control *before* the single plan-level
approval (D-7).

### D-D · "Why this block" reuses UserFacingExplanation (implements D-9)

No build. Documented here so it is not re-opened: any explanation surface the
frontend renders reuses the existing deterministic `UserFacingExplanationNode`
output. Do **not** add a per-block reasoning LLM node.

## Acceptance Criteria

- `UserProfile.resume_text` is optional, round-trips through onboarding, and is
  present in the Strategist's input when set; the real Strategist adapter
  includes it in its prompt and omits it cleanly when `None`. All pre-existing
  fixtures/tests pass unchanged.
- A user can move a proposed block to a new time **and to a different day**; the
  backend re-validates server-side and either persists an adjusted draft (with a
  new canonical hash) or rejects with a typed `reason_code`.
- The server rejects a client-supplied adjustment that overlaps a locked/busy
  window or another block, breaks a hard constraint, violates prerequisite
  order, or falls outside the horizon — **even if the client claims it is
  conflict-free.**
- An adjustment cannot resize a block: end is always derived from the original
  planned duration.
- After an adjustment, `approve` + `write` operate on the adjusted draft, and
  the write-time hash recheck (axiom 06) validates against the adjusted draft —
  no bypass introduced.
- A multi-week plan is proposed, approved, and written across the **entire
  horizon** in a single approval (plan-level), proven by a test.
- Adjusting an already-approved run is refused with a typed reason, not a silent
  mutation.

## Test Expectations

- **Résumé:** profile with/without `resume_text` validates; onboarding form
  round-trip preserves it; Strategist input carries it. A negative test confirms
  `None` produces no prompt artifact.
- **Drag-adjust happy paths:** intra-day move; **cross-day move**; multiple
  simultaneous overrides; untouched tasks unchanged.
- **Drag-adjust rejections (typed `reason_code`, server-authoritative):**
  overlap with a locked/busy event; overlap with another draft block;
  before/after hard-constraint violation; `max_daily_study_min` exceeded;
  disallowed-weekend move; prerequisite-order violation; out-of-horizon move;
  duration-tamper attempt (end ignored / recomputed).
- **Hash + approval:** the canonical hash changes after a successful adjustment;
  approve records the adjusted hash; write rechecks it; tampering with the draft
  after approval surfaces `APPROVAL_HASH_MISMATCH` (reuse the existing axiom-06
  adversarial test pattern).
- **Horizon/plan-level:** multi-week propose → single approve → write covers
  every entry.
- **Boundaries:** `make boundaries` stays green — the adjust service lives in the
  composition-root/app layer and reuses `validation/`, `scheduler/` windows,
  `prerequisites/`, and `contracts/` across the existing seams (no region imports
  a sibling region).

## Explicit Non-Goals

Per the decisions above — listed so they are not silently re-scoped:

- Admissions product surfaces or contracts (D-1, D-2): transcript/GPA parse,
  current-term courses, applicant profile, essay/supplement milestones, decision
  plans.
- A résumé-parser LLM node and its extract→review→confirm gate (D-3) — deferred
  below.
- 60-second undo window / finalize sweep (D-4).
- Motivation-profile capture; the Accountability dashboard staying empty-state
  is intended (D-5).
- Per-block accept / mark-done / reschedule as separate calendar writes (D-7) —
  plan-level only.
- Per-week / selective-week approval (D-8).
- A per-block reasoning LLM node (D-9).
- Agent dock: thread, tool-call log, slash commands, `/mock` generation (D-10).
- Permission / mentor / sponsor sharing surface (D-11).

## Deferred / Future Work — Résumé Parser Node (documented per D-3)

Recorded now so the future build has a starting point; **not** part of this
phase, and gated on an architecture decision.

- **What it is.** An LLM node that reads the pasted/uploaded résumé and proposes
  structured fields (role, experience, stack, target companies, inferred weak
  spots) for the user to **review and confirm** before they are written to the
  profile — the `design-loop/onboarding.jsx` step-5 "AI · please review" card,
  with confidence tiers (extracted fact / inferred guess / auto-suggested).
- **Why it is deferred.** It is a **new LLM node class**, which axiom 01
  currently forbids (only Strategist / Planner / ReflectionSummary /
  UserFacingExplanation are allowed). Adding it requires updating
  `01-system-boundaries.md`, the `.importlinter` contract, a new
  `docs/specs/*.schema.md` for its output, valid/invalid fixtures, and the
  confidence-tier representation — a deliberate, separately-approved change.
- **How this phase prepares for it.** D-A stores the résumé as `resume_text` and
  routes it to the Strategist. When the parser lands, it consumes the same
  `resume_text`, emits a reviewable proposal, and the confirmed fields upsert
  into the profile through a review gate — the raw text remains the fallback for
  users who skip the parse.
- **File storage.** This phase stores text only. A real file upload (PDF/DOCX)
  with private, user-scoped, no-training storage is part of the parser work, not
  this phase.
