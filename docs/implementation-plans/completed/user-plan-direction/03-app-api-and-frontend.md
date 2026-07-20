# PD-C — App, API, and Frontend

## 1. Backend app layer: verification only

`CycleService.onboard` (`app/cycle.py:318`) validates the raw payload
straight through `OnboardingRecord.model_validate` → `UserProfile`, so
the new contract field flows with **zero app-layer code**. Verify, don't
assume:

- One cycle-level test: onboard with `plan_direction` set → stored
  profile carries it; onboard without → `None`; re-onboard replacing a
  set value with `null` clears it (profile edits are the rebuild path).
- The onboard trust boundary (`app/web/routes_cycle.py:14` — server
  overwrites `user_id`) is untouched. **No new endpoints.** The extract
  endpoint (`/onboard/extract`) does not gain the field.
- `_propose_fresh` passes the whole profile to the Strategist
  (`app/cycle.py:576`) — nothing to thread. One E2E-ish assertion via
  the fake transport that a fresh propose's Strategist prompt contains
  the labeled block when the stored profile has the field (this pins
  the store → propose → prompt path, not just the adapter unit).

## 2. Frontend types (`frontend/src/api/types.ts`)

Both `resume_text` sites gain a sibling:

- Profile shape (`:61` region): `plan_direction: string | null`.
- Onboard form/request shape (`:99` region): `plan_direction: string`.

## 3. Shared constant (`frontend/src/lib/intake.ts`)

`RESUME_MIN_CHARS` lives here; add
`export const PLAN_DIRECTION_MAX_CHARS = 4000` beside it. The value
mirrors the backend contract constant; a comment should point at
`contracts/user_profile.py` as the source of truth.

## 4. Onboarding screen (`frontend/src/screens/Onboarding.tsx`)

New optional textarea near the résumé box (`:517-546` is the pattern —
controlled value, `onChange` via `set(...)`), with:

- Label: "Already have a plan? (optional)".
- Helper copy that sets expectations about constraint compression:
  "Paste your own plan or the first steps you want to take — we'll
  adapt it to your weekly hours and timeline." (Constraints win over
  the pasted plan; the copy must not promise verbatim adoption.)
- `maxLength={PLAN_DIRECTION_MAX_CHARS}` plus a live character counter
  once the user is past ~80% of the cap (house style: the résumé box
  shows a threshold hint at `:544-546`; match its tone).
- Submit mapping (`:241` region): trim; empty → `null`, never `""`
  (the contract rejects `""` by design — `min_length=1`).
- Re-onboard hydration: the onboarding form is the profile-edit
  surface. Verify the form prefills `plan_direction` from the current
  profile the same way it does `resume_text`; if the screen doesn't
  hydrate `resume_text` today, match whatever it does — do not invent
  a new hydration path for one field.

## 5. Frontend tests (vitest)

- Types compile (`npm run typecheck` covers the two `types.ts` sites).
- Submit-mapping test: trimmed-empty → `null`; a set value passes
  through verbatim; value at the cap allowed (mirror the existing
  résumé threshold test if one exists in `client.test.ts` /
  `intake.test.ts`; otherwise add to `intake.test.ts`).
- No rendering of the value outside the controlled textarea — the field
  must never be interpolated into any non-escaped sink (React's default
  escaping is the mitigation; the test is a grep-level review item in
  PD-D, not a vitest case).
