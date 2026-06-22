# Phase: Loop MVP — Frontend (the hi-fi product surface)

Build the real **Loop** product UI from the hi-fi design
(`docs/design-reference/design-loop/`) as a React + Vite SPA that consumes the
existing JSON API. The backend phase (`phase-loop-mvp-backend.md`, merged) wired
the few engine gaps the design needed (drag-to-adjust, résumé capture,
full-horizon write); this phase builds the client that drives them and fills the
small JSON-API gaps that client requires.

The landing/marketing page is a **separate** plan: `phase-loop-landing.md`.

## Status

Planned, not started. Scope and stack locked with the product owner
(2026-06-21): React SPA + Vite; **core loop only**; standalone reframed landing
in its own phase. The overshoot the design shows is **not** built (see
Decisions / Non-Goals).

## Decisions (authoritative for this phase)

- **F-1 · Stack = React + Vite + TypeScript SPA.** A new `frontend/` project at
  the repo root (sibling to `backend/`), built to `frontend/dist/` and served by
  FastAPI as static assets. The Python core and its `.importlinter` boundaries
  are untouched. **Installing the Node toolchain / npm dependencies needs
  explicit user approval at execution time** (CLAUDE.md "Ask before installing
  new dependencies"); the *approach* is approved, the *install* is confirmed when
  F-D starts.
- **F-2 · The SPA is a thin client. No control-plane logic moves to the
  browser.** Routing, validation, scheduling, prerequisite computation, approval
  gating, the payload-hash recheck, calendar writes, verification, and rollback
  all stay server-side in `CycleService` and the deterministic core. The frontend
  *renders state and sends intents*; it can never bypass an axiom-06 invariant
  because it has no privileged path — every mutation is a normal `/api` call
  subject to the same server checks the operator CLIs are. This is the project
  thesis at the UI layer: the UI proposes, deterministic infra disposes.
- **F-3 · Scope = core loop only.** In: onboarding wizard → generation →
  draft + drag-to-adjust → approval gate + write/verify → today/check-in →
  accountability (empty-state) → thresholds (read-only). Deferred steady-state
  surfaces (replan/recovery choice, multi-week horizon view, plan-version diff,
  live drift/nudge/recommitment) are **out of this phase** — tracked in
  "Deferred / Future Work".
- **F-4 · The design overshoots the MVP; the overshoot is NOT built.** The hi-fi
  screens show features the backend phase explicitly scoped out. Each is dropped
  to match the already-merged backend decisions, not re-litigated:
  - **No résumé extract→review→confirm card** (design `onboarding.jsx` step 5).
    Résumé is a single "paste raw text (optional)" field that round-trips through
    `/api/onboard` into `UserProfile.resume_text` (backend D-3). No parser node,
    no confidence-tier review UI.
  - **No 60-second timed undo / "Undo" banner** anywhere (design `schedule.jsx`
    and `generation.jsx`). The rollback *primitive* exists, but the time-bounded
    undo deadline + finalize sweep + undo endpoint were not built (backend D-4),
    so there is no undo affordance to wire.
  - **No per-block accept / mark-done / reschedule as calendar writes** (design
    `calendar.jsx` day rail). Approval is **plan-level** (backend D-7).
    Completion *telemetry* (check-in Complete/Missed) is in scope and is **not** a
    calendar write — it is the feedback loop the engine already supports.
  - **No per-week / "approve weeks 5–6" approval** (design `accountability.jsx`
    `MultiWeekNav`). Approve/write covers the **whole horizon** in one unit
    (backend D-8).
  - **No agent dock** — no thread, tool-call log, slash commands, `⌘K`, or
    "Talk to agent" actions (design `agent.jsx`; backend D-10).
  - **No per-block "why" reasoning node.** Any explanation surface reuses the
    existing plan-level `UserFacingExplanationNode` output (backend D-9).
  - **No milestone/"Pipeline" track** — there is no backend milestone contract in
    the MVP (design `calendar.jsx` `MilestoneBar`).
- **F-5 · Connect-Google is the entry gate, not a final wizard step.** The
  session-derived `user_id` trust boundary (`deps.require_user`) means a user is
  already authenticated before any `/api/onboard` call. So the OAuth handshake
  happens **first** (landing CTA / app gate → `/auth/login` → `/auth/callback`),
  and the design's step-7 "Connect" becomes a *connection-confirmed* state, not
  the OAuth trigger. The wizard collects the profile after connect.
- **F-6 · Design fidelity rules.** Reuse the design tokens and component
  language (`design-loop/app.css`: ink/clay/sage/gold palette, Newsreader serif +
  Hanken Grotesk sans). **Drop the fixed `1440×900 .app` shell** — the real app
  is responsive. Brand is **Loop** (the `ProductTopbar` "L" mark), not the stale
  "Tandem" string left in the design CSS comments.
- **F-7 · Develop against the API; cut over once.** Intermediate commits build
  SPA screens runnable via the Vite dev server (proxying `/api` + `/auth` to
  FastAPI), leaving the shipped Jinja pages untouched so every commit stays
  green. The **final** commit (F-H) mounts the built SPA in FastAPI, retires the
  now-redundant Jinja page surface, and migrates the page tests to API tests.

## Required Docs

Read before the relevant deliverable:

- `../../AGENTS.md`
- `../axioms/01-system-boundaries.md` (LLM node classes; UI is not a node)
- `../axioms/06-calendar-safety.md` (the invariants the SPA must not bypass)
- `../axioms/13-concurrency-model.md`, `../axioms/19-always-online-mvp.md`
- `../decisions/ADR-0002-preview-only-calendar-writes.md`
- `phase-loop-mvp-backend.md` + `phase-loop-mvp-backend-handoff.md` (the locked
  D-1…D-11 decisions this phase honors; the `/api/adjust` contract)
- `../specs/draft-schedule.schema.md`, `../specs/scheduler-output.schema.md`,
  `../specs/validation-result.schema.md`, `../specs/user-profile.schema.md`,
  `../specs/approval-event.schema.md`, `../specs/calendar-event-mapping.schema.md`
- The hi-fi screens being ported: `../design-reference/design-loop/onboarding.jsx`,
  `generation.jsx`, `schedule.jsx`, `accountability.jsx` (check-in only),
  `app.css`. (`agent.jsx`, `calendar.jsx` per-block rail, and the overshoot in
  the others are reference-only — not built, per F-4.)
- Current surface this phase consumes/replaces:
  `backend/src/agentic_calendar/app/web/{routes_cycle.py,routes_auth.py,deps.py,pages.py}`

## Already Complete vs. Genuinely New (verified against code, 2026-06-21)

The backend is essentially done; this phase is **almost entirely frontend**. The
one new backend commit (F-A) is thin JSON glue, not engine work. Verified by
reading `routes_cycle.py`, `routes_auth.py`, `pages.py`, `results.py`.

**Already complete — do NOT rebuild:**

- **All calendar-safety gates** (axiom 06; Phases 2 + 9): approval gate,
  `approval_event_id`, payload-hash recheck, write, per-event verification,
  auto-rollback on verify-failure, duplicate detection. F-F is **UI over this**,
  not gate work.
- **Auth trust boundary** (hosted Increment 1 / Phase 9): `/auth/login` (PKCE +
  state) → Google → `/auth/callback` (tester allowlist, dedicated-calendar
  provisioning, session `user_id`/`email`) → `/auth/logout`; `require_user`
  resolves the acting user server-side. The SPA *links into* this redirect flow;
  it does not reimplement it. F-B's "session handling" is only client
  redirect-on-401.
- **Drag-to-adjust BACKEND** (Loop backend phase, merged): `POST /api/adjust`,
  server-side re-validation, cross-day moves, typed `reason_code`s. F-E is **UI
  over this**.
- **Résumé capture (`resume_text`), full-horizon plan-level write** (Loop backend).
- **Threshold change-log + `tuning.toml`** (Phase 9): read-only view in F-G.
- **A working Jinja UI** (`pages.py`; frontend follow-ups) already covers onboard,
  today/check-in, accountability (empty-state), thresholds, and
  draft→approve→write. This phase **replaces it with React** (Jinja opt-out) and
  retires it in F-H. **Jinja is not used by the new frontend.**
- **JSON mutation API** (`routes_cycle.py`): `POST /api/{onboard,propose,adjust,
  approve,write,ingest}`, `GET /api/status`.

**Genuinely new (what this phase builds):**

- The React/Vite SPA itself — no `frontend/` exists (F-B…F-G).
- The **drag-to-adjust UI** and the **generation-pipeline UI** — neither was ever
  built; the shipped Jinja surface has no drag screen and no pipeline view
  (F-E, F-D).
- **One thin backend commit (F-A)** exposing as JSON what the SPA needs but the
  API doesn't yet return: verified gap — `ProposeResult`/`AdjustResult` return
  `draft_schedule_id` + `draft_payload_hash` but **not the block entries or the
  imported free/busy**, so the grid has nothing to render from; and today /
  accountability / thresholds / profile projections exist only as Jinja HTML.
- The standalone landing page (separate plan, `phase-loop-landing.md`).

**Considered and dropped:** a CSRF token on `/api` mutations. The session cookie
is `SameSite=lax`, which already blocks cross-site cookie-bearing POSTs, so this
is defense-in-depth, not a correctness gap — see "Deferred / optional hardening".

## Deliverables (one commit each)

### F-A · JSON the SPA reads from (backend; thin — exposes existing logic as JSON)

The only new backend commit. No engine logic — it surfaces, as JSON, projections
that already exist (in `CycleService`/`env`, or computed today inside the Jinja
handlers as plain Python):

- `GET /api/draft` — the pending draft's **entries** + `canonical_payload_hash` +
  `hash_canonicalization_version` **+ the imported free/busy** for the grid.
  Necessary because `ProposeResult`/`AdjustResult` return only the id + hash, not
  the blocks or busy windows the drag screen (F-E) and gate (F-F) render.
- `GET /api/today` — scheduled-task rows, tz-localized, `due`/`reported` flags
  (the `_today_rows` computation, relocated out of the Jinja handler).
- `GET /api/accountability` — `accountability_snapshot` + `has_motivation_profile`
  (stays empty-state per backend D-5).
- `GET /api/thresholds` — effective tuning sections + change-log history.
- `GET /api/me` — current `UserProfile` values + `timezone` + `email` for the
  wizard's prefill / edit-later.
- `POST /api/checkin` (`{task_id, outcome}`) — the guarded check-in. Move the
  membership / "due" / idempotency guard out of the Jinja `ui_checkin` handler
  into a shared place so the SPA can't bypass it (no double-count, no non-due or
  foreign task), then ingest via the existing path. (Without this the SPA would
  hit raw `/api/ingest` and skip the guard.)

Return existing contracts where they exist; view-models (today row, threshold
row) are **unregistered response DTOs** — no generated JSON schema, mirroring the
request-DTO precedent (`DraftAdjustment`, `FreeBusyInterval`). Tests in
`tests/web`: each projection matches its page data; the check-in guard
(double-submit / non-due / foreign refused; happy complete + miss).

### F-B · Vite + React + TS scaffold: shell, tokens, API client, session handling (frontend infra)

**[Requires user approval to add the Node toolchain / npm deps before install.]**

- Create `frontend/` (Vite + React + TypeScript). Vite dev server proxies
  `/api` and `/auth` to FastAPI for local dev (no FastAPI change yet).
- Port `design-loop/app.css` tokens into the app stylesheet; set up the Loop
  brand + `ProductTopbar`; load the same fonts the design uses. Responsive — drop
  the fixed `1440×900` shell (F-6).
- Typed API client (`src/api/`): `fetch` with `credentials: 'include'`, surfacing
  typed `reason_code` results distinctly from transport errors (mirrors how the
  API separates a workflow failure-with-`reason_code` from a 409 precondition
  error).
- **Session handling (client only — backend auth is already complete):** an
  unauthenticated `/api` call (401) redirects to `/auth/login`; "Log out" POSTs
  `/auth/logout`; identity from `/api/me`. No backend auth is built here.
- A minimal routed shell (topbar + empty views) proving the wiring end-to-end.
- Frontend gate added here: `tsc --noEmit`, lint, and `vite build` must pass
  (these join the per-commit checks for F-B…F-G).

### F-C · Onboarding wizard (frontend)

Port `onboarding.jsx` as the deterministic multi-step wizard: Goal → Time budget
& constraints → Deadline → Skills/cadence → **Résumé (paste raw text, optional —
NO extract/review card, F-4)** → Targets → Connect (shows connection confirmed
per F-5). Submits the full `UserProfile` (+ `timezone`) via `/api/onboard`;
prefills from `/api/me`; surfaces typed `ValidationError`s per field rather than
opaque errors. The contract is the single validation oracle — the wizard does no
parsing beyond CSV/checkbox shaping (parity with `pages._build_profile`).

### F-D · Generation pipeline + typed-failure recovery (frontend)

Port `generation.jsx` `GenerationProgress` + `FailureGallery`: trigger
`/api/propose` (free/busy fetched server-side already), show the deterministic
pipeline (Strategist → Planner → Validation → Scheduler) and the ≤2 repair-loop
framing. On a workflow failure, render the typed `reason_code` in the design's
three-part shape — what / why / recovery affordances — for the real codes
(`INSUFFICIENT_WEEKLY_CAPACITY`, `USER_FIT_VIOLATED`, `REPAIR_LIMIT_EXCEEDED`,
`COVERAGE_INCOMPLETE`, `LLM_REFUSAL`, …). Recovery actions map to real intents
(re-onboard to relax a constraint, re-propose); no dead ends.

### F-E · Draft review — drag-to-adjust grid (frontend; the signature interaction)

Port `schedule.jsx` `ScheduleReview`: the time grid with **draggable proposed
blocks** (snap 15 min, move across days) and **fixed, translucent imported
Google-Calendar events**. On drop, send the moved blocks to `POST /api/adjust`
and **re-render from the server's response** — the server is authoritative
(backend D-6: it re-validates every adjustment, never trusts client
conflict-checking). The client's optimistic snap-back is cosmetic only; a move
the server rejects returns a typed `reason_code` shown inline, and the truth is
the persisted adjusted draft (new `canonical_payload_hash`). **No 60s undo**
(F-4). Cross-day moves explicitly supported.

### F-F · Approval gate + write + verification (frontend; UI over the COMPLETE backend gate)

The backend gate (approval, hash recheck, write, verify, rollback) is already
done — this is purely its UI. Port `generation.jsx` `ApprovalGate`: the confirm
modal shows target calendar,
event count, the `payload_hash`, and "rechecked at write time"; `Approve` →
`/api/approve` then `/api/write`. Render the verification result (N/N verified).
On verification failure, surface `CALENDAR_VERIFICATION_FAILED` and that the
engine **auto-rolled-back** the unverified events (existing write-path behavior).
**No manual "roll back all" button and no timed undo** — that is the undo
endpoint backend D-4 deliberately did not build (F-4). This screen is the only
place the product writes to a calendar; it cannot proceed without
`approval_event_id` + the hash recheck because those live in the service.

### F-G · Steady-state read views: Today / check-in, accountability, thresholds (frontend)

- **Today**: render `/api/today`; Complete/Missed posts to `/api/checkin` (F-A).
  Completion telemetry only — not a per-block calendar write (F-4).
- **Accountability**: render `/api/accountability`, **empty-state first** (no
  motivation profile yet → "Accountability isn't set up") per backend D-5,
  distinct from "no active plan yet".
- **Thresholds**: render `/api/thresholds`, read-only (axiom 07 — tuning changes
  only via `tuning.toml`).

### F-H · Cutover: serve the SPA, retire the Jinja surface, migrate tests (backend + integration)

- Mount the built `frontend/dist/` in FastAPI via `StaticFiles` with SPA-routing
  fallback (serve `index.html` for non-`/api`, non-`/auth` app routes). Routing:
  SPA owns the app routes; `/auth/callback` redirects into the SPA. (Landing at
  `/` is owned by `phase-loop-landing.md`; coordinate the root route there.)
- Retire the now-redundant Jinja page routes + templates (`pages.py` page GETs
  and `/ui/*`), **keeping `/auth`, `/api`, and `/healthz`**. The projection logic
  already moved to `/api` (F-A), so this removes duplication, not behavior.
- Migrate `tests/web/test_pages.py` / `test_app.py` page-and-`/ui` assertions to
  the equivalent `/api` assertions; keep the axiom-06 adversarial tests (they now
  drive `/api`).
- Add an e2e smoke that drives onboard → propose → adjust → approve → write
  through `/api` exactly as the SPA does, asserting the hash recheck holds.

## Acceptance Criteria

- A connected tester completes the whole loop in the SPA: onboard → generate →
  drag-adjust the draft → approve → write, and sees per-event verification.
- The SPA never bypasses an axiom-06 invariant: tampering with the draft after
  approval surfaces `APPROVAL_HASH_MISMATCH`; a write cannot occur without
  `approval_event_id` and the hash recheck — proven against `/api`, not just in
  the UI.
- Drag-to-adjust persists via `/api/adjust`, supports cross-day moves, and a
  server-rejected move shows a typed `reason_code` (the client's local snap-back
  is never the source of truth).
- Résumé is a raw-text field only; no extract/review card exists. A user who
  skips it onboards cleanly.
- None of the overshoot ships: no 60s undo, no per-block accept/done, no per-week
  approval, no agent dock, no milestone track (grep-able absence).
- Every `/api` read endpoint returns the same projection its retired Jinja page
  showed; accountability renders empty-state without a motivation profile.
- `make check` stays green at every backend commit; `tsc`/lint/`vite build` pass
  at every frontend commit; `make boundaries` is unaffected (no Python region
  imports change).

## Test Expectations

- **Backend (F-A, F-H):** read-endpoint projections match the page data;
  `/api/checkin` guard (double-submit / non-due / foreign task refused); retained
  axiom-06 adversarial hash-mismatch test now on `/api`; e2e smoke through the
  full cycle.
- **Frontend:** component/unit tests for the API client (reason_code vs transport
  error), the drag math + server-authoritative re-render, the wizard's
  contract-error rendering, and the approval-gate state machine. Keep these
  deterministic — assert on rendered state and dispatched intents, not prompt/LLM
  prose.

## Explicit Non-Goals

The overshoot (F-4), restated so it is not silently re-scoped: résumé
extract→review parser UI; 60s undo / finalize sweep / manual rollback button;
per-block accept/done/reschedule; per-week / selective-week approval; agent dock
(thread, tool log, slash commands, ⌘K); per-block reasoning node; milestone /
"Pipeline" track.

Deferred steady-state surfaces (F-3) — buildable later because the engine mostly
backs them, but **not** this phase: replan / recovery-mode choice
(`propose` with `recovery_mode`), multi-week horizon **view** (read-only; still a
single full-horizon approve), plan-version diff projection, live
drift/nudge/recommitment (needs the deferred motivation-profile capture).

Also out: native mobile, real-time multi-device sync (always-online single
session per user, axiom 19), any "auto-approve" / "skip-verification" toggle.

## Deferred / Future Work

- **Motivation-profile capture** (still deferred from `phase-frontend-mvp.md`):
  until it lands, the accountability dashboard stays empty-state. Adding it lights
  up the deferred drift/nudge/recommitment surfaces.
- **Steady-state screens** above, once prioritized — each is additive over the
  existing engine, no new contracts beyond a possible plan-diff projection.
- **Résumé parser node** — a new LLM node class (axiom 01 change), the gated
  follow-up documented in `phase-loop-mvp-backend.md`; only then does the
  extract→review card get built.

## Deferred / optional hardening

- **CSRF token on `/api` mutations.** Considered for this phase and dropped: the
  session cookie is `SameSite=lax`, so a cross-site forged POST does not carry the
  cookie and fails `require_user` — the gap the `/ui` CSRF closed for form posts
  does not exist for the SPA's same-origin `fetch`. If a future change weakens
  `SameSite` (e.g. an embedded/cross-site context), add a per-session token
  (reusing the existing `_csrf` mechanism) required as an `X-CSRF-Token` header on
  `/api` mutations. Not built now.
