# 01 · Honest Copy + Identity Links

Effort: ~30 minutes. Do first — one of the two items is a truthfulness bug
on the live page.

## A. Fix the false "automatic rollback" claim (bug, not polish)

**What's wrong.** Two places on the shipped landing page claim behavior the
engine does not have:

- `landing/index.html:585` (step 05, "Write & verify"): "…re-reads every
  event to confirm it, **and rolls back anything it can't**."
- `landing/index.html:612` (trust item "Verified after writing"): "…anything
  unverified is **automatically rolled back**."

The write manager marks unverified events `VERIFICATION_FAILED`, leaves them
on the calendar, and does **not** activate the plan; rollback is a separate,
explicitly-triggered step. Commit `dba497a` ("honest write-failure copy")
fixed this exact claim in the SPA (`frontend/src/lib/approval.ts` →
`writeFailureMessage`) after a bs-detector audit rated it HIGH — the landing
page was written in the same era and slipped through.

**Replacement copy** (truthful on `main` today *and* after the
`ux-quality-pass` B1 recovery UI ships):

- Step 05: "Loop writes to one calendar and re-reads every event to confirm
  it landed. If anything can't be verified, the plan is not activated — you
  see exactly what did and didn't land."
- Trust item: "Each event is re-read after writing. Anything unverified
  blocks the plan from activating — nothing is silently treated as done."

Once the deployed version includes B1 (3-option rollback / retry / keep), a
follow-up sentence may be added: "…and you choose how to recover: roll back,
retry, or keep what landed." Do not add it before that deploy.

**Also sweep while in the file:** re-read every other claim against the
deployed behavior. Verified 2026-07-04: the remaining trust items (approval
gate, hash-check at write time, scoped access, no-training) are accurate;
"Typed failures, never dead ends" (`:624`) is defensible now and becomes
fully true once the B-track ships.

## B. Footer byline + identity links

The page is anonymous. A founder who likes it has no one-click path to the
person. Add to the existing footer (`landing/index.html:670-680`):

- "Built by **Shawn Liu**" linking to the portfolio site.
- A GitHub link (profile or repo, per the README open question).
- Keep it one line in the existing `.foot-inner` flex row; muted styling,
  no new sections.

Optionally mirror a quiet byline near the top nav next to the future
"How it's built" link (added in increment `03`, not here).

**Blocked on:** portfolio + GitHub URLs from the user. If unresolved, ship
part A alone — it must not wait.

## Acceptance criteria

- No sentence on the landing page asserts behavior the deployed engine does
  not have; the rollback claim matches `writeFailureMessage` semantics.
- Footer contains a working byline with at least one external identity link.
- Page remains a single self-contained static file; no layout regressions at
  mobile widths (the `@media (max-width: 820px)` block still applies).

## Explicit non-goals

- No copy rewrite beyond the false claims and the byline — the draft's
  assessment stands: the page is already strong for users.
