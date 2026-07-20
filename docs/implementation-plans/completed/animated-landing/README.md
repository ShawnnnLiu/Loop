# Animated Landing Page Adoption

Status: IMPLEMENTED (2026-07-20, branch `design-drop-loop-landing`).

Outcome notes:

- PR #50 (narrative-pathways) confirmed merged before the swap; `origin/main` was merged into the branch first.
- `landing/index.html` replaced byte-for-byte from the design reference; `how-its-built.html` untouched (already byte-identical).
- Preservation greps all green: 4x `/auth/login`, 3x beta mailto, 2x `/how-its-built`, privacy/terms/Google-permissions/GitHub links, the three scope chips, closed-beta strip, approve-only copy in meta description + og:description + JSON-LD + body, zero em dashes.
- `make test-fast`: 4512 passed.
- CDP browser verification green at 1280px and 375px: scenes 1-5 play once and in order, no user-visible horizontal scroll (`scrollX` pinned at 0; deliberately-offscreen animation content is clipped by `html.anim body{overflow-x:hidden}`), CLS 0, reduced-motion serves static frames without `html.anim`, JS-disabled page fully readable with all OAuth copy present.
- One repo-side fix on top of the verbatim swap: scene-3 approval overlays (`.okov`) overflowed their blocks where the appended checkmark added a wrap line (4 blocks at 375px, 1 at 1280px); the base title now invisibly reserves the checkmark's width so base and overlay wrap identically.

## Context

Design drop 3 (`Admissions Agentic Scheduler (3).zip`, synced into `docs/design-reference/` on 2026-07-20) delivered a finished, scroll-animated rework of the Loop landing page.
The live `landing/index.html` is a static marketing page with essentially no motion; the reworked page turns the same content into a scroll-driven showcase of real product behavior.
This plan covers adopting that page as the live landing without weakening anything Google OAuth verification depends on.

The design docs are already synced (commit `89cbe6d` on `design-drop-loop-landing`).
This doc is the execution plan for the swap itself.

## Source artifacts (read-only)

- `docs/design-reference/uploads/loop-landing-handoff/HANDOFF.md` - the task brief; its "Hard constraints" and "Verify before finishing" sections are the acceptance criteria for this plan.
- `docs/design-reference/uploads/loop-landing-handoff/landing/index.html` - the finished animated page (~850 lines, ~75 KB). This file replaces `landing/index.html` verbatim.
- `docs/design-reference/uploads/loop-landing-handoff/landing/how-its-built.html` - byte-identical to the live `landing/how-its-built.html`; no change needed.
- `docs/design-reference/uploads/loop-landing-handoff/{frontend,backend}/` - source snapshots each scene was modeled on; reference only, never copied anywhere.

Never edit files under `docs/design-reference/`.
If the page needs repo-side adaptation, edit the copy in `landing/` after the swap.

## What was already verified about the new page

Checked during planning (2026-07-20), so execution does not need to re-derive it, only re-confirm after the copy:

- Self-contained: all CSS/JS inline; the only external requests are the same Google Fonts links the live page uses. No build step, no CDN, no canvas/video/Lottie.
- Link inventory is identical to the live page: 4x `/auth/login`, 3x beta-access mailto, 2x `/how-its-built`, `/privacy`, `/terms`, Google permissions link, GitHub link.
- OAuth-verification copy preserved: closed-beta strip, the three scope chips (`email · profile`, `calendar.freebusy`, `calendar.app.created`), "writes to Google Calendar only after you approve" (meta description, og:description, JSON-LD, and body), and "The calendar stays drafts-only until you approve. No exceptions."
- Motion mechanics: five scenes (`data-scene="1..5"` - résumé→evidence, strategist→gates, drafts→approval, evidence→pathways, plus a "sneak peek" mastery-sky scene) driven by two `IntersectionObserver`s, animating transform/opacity only, with a `prefers-reduced-motion` static-frame fallback and full readability with JS disabled (`html.anim` gating).
- The `<title>` uses a plain dash, fixing the em dash in the live page's title.

## Sequencing constraint

The handoff's backend snapshots (`templates/pathways.py`, `contracts/pathway_template.py`, `contracts/resume_extraction.py`) match the `narrative-pathways` branch (PR #50), not `main`.
Scenes 1 and 4 depict NP-series features (typed evidence chips with kind + theme tags; the five pathway templates), and scene 5 previews the Star Atlas.
Adopt the landing only after PR #50 merges and deploys, so the marketing page does not advertise capabilities the deployed product lacks.
Scene 5 is explicitly framed "coming soon" and is fine to ship ahead of the mastery-map work.

## Execution steps

1. Branch off `main` after PR #50 has merged.
2. Copy `docs/design-reference/uploads/loop-landing-handoff/landing/index.html` over `landing/index.html`, byte-for-byte.
3. Re-run the preservation greps (link inventory, scope chips, closed-beta strip, approve copy, no `—` in the copy) against the new `landing/index.html`.
4. Backend checks from `backend/`: the landing routes are covered by `backend/tests/web/test_server.py` (and `test_spa.py` for route precedence); run `make test-fast`.
   No backend change is expected - `/` serves `landing/index.html` by path (`app/web/app.py`, overridable via `LANDING_INDEX`).
5. Browser verification per HANDOFF.md, using the in-house CDP smoke recipe (see `docs/implementation-plans/completed/ux-quality-pass/README.md` and the ux-quality-pass memory) against the dev backend on `:8000`:
   - scroll the full sequence; triggers fire once and in order;
   - `prefers-reduced-motion` renders static final frames (CDP: `Emulation.setEmulatedMedia` features);
   - 375 px viewport: no horizontal scroll, no layout shift from animations;
   - JS disabled: page reads as static sections;
   - screenshots of each scene at rest and mid-animation for the PR.
6. Commit, push, open a PR.

## Rollback

The swap is a single-file change: `git revert` restores the old page.
In a deployed emergency, `LANDING_INDEX` can repoint the route at any file without a code change.

## Kickoff prompt for the implementation session

> Read `docs/implementation-plans/animated-landing/README.md` and `docs/design-reference/uploads/loop-landing-handoff/HANDOFF.md`, then execute the plan: replace `landing/index.html` with the animated page from the design reference, run the preservation greps, `make test-fast` from `backend/`, and the CDP browser verification (full scroll, reduced motion, 375 px, JS off).
> Confirm PR #50 (narrative-pathways) is merged first; stop and ask if it is not.
> Commit at the end of each increment.
