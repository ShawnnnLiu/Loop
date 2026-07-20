# 03 · "How It's Built" Page

The highest-leverage permanent artifact: the page where the invisible
engineering becomes visible without sign-in. Linked from the landing nav and
footer.

## Form

- A second self-contained static file, `landing/how-its-built.html`, same
  inlined design tokens and fonts as `landing/index.html` (L-1 pattern: no
  build step, no external assets).
- Served at `GET /how-its-built` by a route registered next to the landing
  route in `backend/src/agentic_calendar/app/web/app.py:160-164` — it must be
  added **before** `_mount_spa`'s catch-all (`app.py:62-79`) or the SPA will
  swallow it. Follow the landing pattern: a `FileResponse` with the path
  supplied by the composition roots (`app/web/server.py:57-64`,
  `app/web/__main__.py:51`), env-overridable like `LANDING_INDEX`.
- Landing gets a nav link ("How it's built") next to "How it works"
  (`landing/index.html:486`) and a footer link.
- The architecture diagram is **inline SVG** (hand-authored, tokens-colored)
  so the page stays self-contained.

## Content outline (each section names where its claims are checkable)

1. **The thesis and the boundary.** "LLMs propose. Deterministic
   infrastructure disposes." One diagram: the four LLM node classes
   (`Strategist`, `Planner`, `ReflectionSummary`, `UserFacingExplanation`)
   inside a small "propose" box; routing, validation, scheduling, approval,
   calendar writes, telemetry, drift — all outside it, deterministic.
   Source: `docs/axioms/01-system-boundaries.md`, ADR-0001, ADR-0006.
2. **Safety architecture.** Approval-ID-gated writes; the
   `approved_payload_hash` recheck against the live draft at write time;
   dry-run / verification-read / rollback support on every side effect;
   typed `reason_code` on every failure; immutable plan versions; injected
   clock and IDs. Source: axiom 06, axiom 16, `docs/specs/approval-event.schema.md`.
3. **The eval harness** (the differentiator for engineers): live capture →
   committed recordings → deterministic re-grading gating CI
   (`make eval-gate`, a separate CI job); Tier-1 deterministic graders +
   Tier-2 LLM judge that is advisory-only and deliberately not a workflow
   node; prompt versioning with pinned byte hashes so a prompt edit cannot
   ship unmeasured. Source: axiom 22 (as amended 2026-07-04),
   `backend/Makefile` `eval-gate`, `tests/llm_nodes/test_prompt_versions.py`.
4. **The numbers, stated plainly** — re-verify every one at ship time; the
   2026-07-04 values on branch `ux-quality-pass` were: `make check` → 2691
   backend tests green; 81 frontend tests; 23 axiom documents (00–22);
   8 ADRs; per-node cost caps with ~$1.70/month expected spend under an
   $8/month cap; ~$0.28 per onboarding, ~$0.22 per replan cycle (axiom 09).
   State plainly that validation/drift thresholds and confidence scores are
   **heuristic priors until calibrated** — the axiom-08 honesty rule applies
   to this page as much as to the UI.
5. **Links.** The engineering blog posts (if they exist — README open
   question 4), the repo (if public — open question 2, otherwise "code
   walkthrough available on request"), and the portfolio site.

## Voice

Same register as the landing: plain sentences, no superlatives. The page
convinces by being checkable, not by adjectives. Numbers get one sentence of
context each, not a wall of stats.

## Test / verification

- Backend: one route test asserting `/how-its-built` returns the file and
  that the SPA catch-all still serves app routes (pattern: existing landing
  route tests near the `app/web` tests).
- Link check: every `href` on both static pages resolves (relative anchors,
  `/auth/login`, the new page, external links).
- Responsive spot-check at mobile widths.

## Acceptance criteria

- A visitor can go landing → How it's built → author links without sign-in.
- Every number on the page was re-measured in the shipping commit (record
  the commands in the commit message: `make check`, frontend test run,
  `ls docs/axioms | wc -l`, `ls docs/decisions | wc -l`).
- No claim of calibrated accuracy anywhere (axiom 08 public-facing rule).

## Explicit non-goals

- Not a blog platform — posts live elsewhere and are linked.
- No interactive demos on this page (that's `04`/`05`).
