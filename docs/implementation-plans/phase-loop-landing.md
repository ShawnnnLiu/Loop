# Phase: Loop Landing Page

A standalone marketing/landing page for **Loop**, the interview-prep /
job-search productivity scheduler. Reuses the design system's visual language
but is **reframed for Loop productivity** — the existing landing design
(`docs/design-reference/landing/`) is the *old admissions product* ("Tandem 同舟",
parents/students, bilingual) and is reference-only, not the content.

Companion to `phase-loop-mvp-frontend.md` (the product SPA). Kept separate
because it is a different, simpler surface (a static page, not the app) and can
ship independently.

## Status

Planned, not started. Locked with the product owner (2026-06-21): standalone
reframed Loop landing, English-only, productivity framing, CTA into the app's
Google connect.

## Decisions (authoritative for this phase)

- **L-1 · Standalone static page.** Plain HTML/CSS (+ minimal vanilla JS if
  needed), not part of the React/Vite app build — mirroring how the reference
  landing is authored. Reuses the same design tokens so it is visually
  consistent with the SPA. Served by FastAPI as a static asset.
- **L-2 · Framing = Loop / productivity, English-only.** Loop is the
  interview-prep / job-search scheduler (productivity framing, per the backend
  phase's D-1/D-2). **Drop** the admissions narrative entirely: no
  parents/students doors, no transcript/GPA/essays/school-list, no bilingual
  EN/中文 toggle, no "$8,999 agency" comparison. Keep only the *visual* language
  (layout, tokens, mock cards) — rewrite all copy.
- **L-3 · The story is the project thesis.** The page sells what the engine
  actually guarantees: **the approval gate (no silent calendar writes)**, the
  **deterministic propose→dispose pipeline** (LLMs propose structured candidates;
  deterministic code validates, schedules, and writes), **honest progress**
  (telemetry-driven calibration), and **privacy** (your résumé/data stay on your
  account, never used for training). Do not promise the overshoot the product
  does not ship (no "undo anytime", no agent chat, no per-week approval claims).
- **L-4 · CTA = Connect Google / Get started → `/auth/login`.** The single
  primary action enters the real OAuth flow (the app's entry gate, per frontend
  F-5). Honest about limited testing: mention the ≤100-tester allowlist near the
  CTA so a non-allowlisted visitor isn't surprised by the `/auth/callback` 403.
- **L-5 · Routing.** Landing is served at `/` for the marketing surface; the SPA
  owns the app routes (coordinated in frontend F-J). Simplest split: landing at
  `/`, "Get started" → `/auth/login` → callback → the app. No session-conditional
  rendering at `/`.

## Required Docs

- `../../AGENTS.md`
- `phase-loop-mvp-backend.md` (D-1/D-2 productivity framing; the guarantees to
  market truthfully)
- `phase-loop-mvp-frontend.md` (F-5 connect-as-gate; F-J root-route coordination)
- `../axioms/06-calendar-safety.md` (the approval-gate / no-silent-writes promise)
- `../design-reference/landing/` (visual reference only — copy is not reused)
- `../design-reference/design-loop/app.css` (the shared design tokens)

## Deliverables (one commit each)

### L-A · Landing content + structure (reframed hero + trust story)

Build the static page reusing the design tokens:

- **Hero**: Loop value proposition — interview prep / job search, scheduled
  around your real calendar and kept honest. Primary CTA "Connect Google
  Calendar / Get started" + the ≤100-tester note (L-4). A product mock reusing
  the design's card/calendar visuals (a week of proposed blocks + an "Approve"
  affordance) — restyled, not the admissions parent/student stack.
- **How it works**: the loop — onboard (deterministic form + optional résumé) →
  generate (AI proposes a plan) → review & adjust (drag) → **approve** → write to
  Google Calendar → check in → calibrate. Make the approval gate the hinge.
- **Trust / safety strip**: no silent calendar writes; you approve every write;
  the payload is hash-checked at write time and every event is verified after;
  your data stays on your account and is never used for training; revocable
  Google access scoped to one calendar.
- **Thesis line**: "LLMs propose. Deterministic infrastructure disposes." — what
  the engine is, in one line.
- **What it is NOT** (optional, honest framing): not an autonomous calendar
  assistant, not a chatbot — it never acts without your approval.
- **Footer**: minimal — brand, one-line tagline, contact/waitlist link.

English-only; no bilingual toggle, no admissions sections (L-2).

### L-B · Serve, integrate, responsive, checks

- Serve the landing as the unauthenticated entry at `/` (coordinate with frontend
  F-J so the SPA and landing don't fight over the root; landing at `/`, app at its
  own routes).
- Make the CTA(s) link to `/auth/login`; confirm a logged-out visitor reaches
  Google consent and an allowlisted account lands in the app.
- Responsive pass (the reference is desktop-fixed; the landing must work on
  mobile widths). Verify fonts/tokens match the SPA.
- Lightweight check: HTML validates, links resolve, no broken asset paths; if any
  JS is added (e.g. a smooth-scroll), keep it dependency-free.

## Acceptance Criteria

- The page is unmistakably **Loop / productivity** — zero admissions copy, no
  bilingual toggle, no parents/students framing.
- Every claim is true to the shipped product: it markets the approval gate,
  deterministic pipeline, verification, and privacy — and does **not** advertise
  undo-anytime, agent chat, or per-week approval.
- The primary CTA enters the real `/auth/login` flow; the tester-allowlist limit
  is stated near the CTA.
- Served at `/` for logged-out visitors without conflicting with the SPA routes;
  responsive on mobile and desktop; visually consistent with the app via shared
  tokens.

## Explicit Non-Goals

- No admissions product surfaces or copy (transcript/GPA, essays, school list,
  parents/students doors), no bilingual EN/中文 (L-2).
- No marketing claims for features the MVP doesn't ship (60s undo, agent dock,
  per-block/per-week approval).
- No separate React app for the landing — static page only (L-1).
- No analytics/tracking, A/B testing, or CMS in this phase.
