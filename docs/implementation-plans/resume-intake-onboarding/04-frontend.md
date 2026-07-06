# RI-D · Frontend — Consolidated Step with Extract

One commit. All in `frontend/src`. Visual target:
`docs/design-reference/design-loop/onboarding.jsx` step 5 (the "AI · please
review" card), adapted to paste-only and the consolidated layout.

## 1. Wizard consolidation (locked decision 2)

`Onboarding.tsx` (`STEP_LABELS` at `:17`) goes from
`Goal → Time & constraints → Skills → Résumé & targets → Connect` (5 steps)
to **4 steps**:

1. `Goal` — unchanged.
2. `Time & constraints` — unchanged.
3. `Résumé & profile` — the consolidated step (below). Absorbs the old
   Skills step (weak/strong areas) and the old Résumé & targets step.
4. `Connect` — unchanged.

Deep links: `?step=N` (`:203-208`) shifts meaning. Grep the SPA for
`?step=` / `step=` navigation sources (Tuning screen, profile-edit links)
and update indices; add a vitest for the mapping so a stale link cannot open
the wrong step silently.

## 2. The consolidated step

Layout (top to bottom):

- **Résumé paste**: the existing textarea (`:497-512`) with its privacy note.
- **Extract button** (locked decision 3): explicit, disabled while the
  textarea is empty or a request is in flight; label "Extract from résumé";
  spinner + "Reading your résumé…" while pending. Re-extract is allowed (the
  design-reference "Looks wrong, redo" affordance).
- **Five editable sections**, each usable with or without extraction:
  - `Experience` — row editor (title, organization, summary), add/remove.
  - `Skills` — chip input. After extraction, canonical skills
    (`skills_canonical` display names) render as normal chips;
    `skills_unmatched` surfaces render in a visually distinct
    "not recognized" group with a one-line explainer ("Found in your résumé
    but not in our skill vocabulary — keep or remove") and a keep/remove
    affordance per chip. Manual free-text entry stays allowed — the
    vocabulary constrains the AI, not the user.
  - `Strong areas` (`known_strengths`) — chip input.
  - `Weak areas` (`known_weaknesses`) — chip input; when last populated by
    extraction, show the mockup's "a guess" flag + one-line explainer
    ("Inferred from your résumé — edit freely").
  - `Target companies or categories` (`target_companies`) — chip input;
    extraction proposes categories, the user may type company names.
- `Target level` — stays a manual text field (never auto-filled).

Provenance labels are per-section and structural (README table): Experience
and Skills = "extracted", Strong/Weak areas = "inferred", categories =
"suggested". No per-chip confidence UI.

### Merge policy on Extract

Pressing Extract replaces the contents of the five auto-fillable sections
with the proposal (`inferred_weak_spots` → Weak areas,
`target_company_categories` → the targets list). If any of those sections
already has user-entered content, show an inline confirm ("Replace your
current entries with the extracted ones?") before overwriting — never
destroy hand-typed input silently. Extraction state is client-only until the
wizard finishes; copy stays honest: "Nothing is saved until you finish
setup."

### Failure and fallback

On a non-ok result, show an inline error banner: friendly copy + the typed
`reason_code` in the detail line (existing SPA error-surface pattern), keep
all sections manually editable, keep the wizard navigable. Skipping the
résumé entirely must remain exactly as functional as today.

## 3. API client and types

- `api/types.ts`: `ExperienceItem`, extend the TS `UserProfile` mirror
  (`:33-54`) with `experience` + `skills`; add `ExtractResumePayload`,
  `ResumeExtraction`, `ExtractResumeResult` (incl. `skills_canonical`,
  `skills_unmatched`, `taxonomy_version`).
- `api/…`: `extractResume(payload)` → `POST /api/onboard/extract`.
- `buildPayload` (`Onboarding.tsx:99-139`): include `experience` (structured
  rows) and `skills` (csv→array like the existing list fields).
- `initialForm(me)` (`:54-90`): prefill both new fields for edit-later.

## 4. Tests (vitest)

- Merge policy: proposal fills empty sections; overwrite-confirm gates
  non-empty ones; edits after extraction survive re-render.
- Payload round-trip: `initialForm` → edit → `buildPayload` carries
  `experience`/`skills` correctly (incl. empty cases).
- Extract flow with a mocked client: pending state disables the button;
  failure renders the reason_code banner and leaves the form editable.
- Step-index mapping test for the 5→4 consolidation.

Gates: `npm run typecheck && npm run lint && npm run test && npm run build`
from `frontend/`; then a real-browser pass against the keyless dev server
(`python -m agentic_calendar.app.web`) using the CDP smoke-harness recipe
from the ux-quality-pass session — paste, extract, edit a chip, delete an
experience row, finish, reload, verify `/api/me` echoes exactly the
confirmed values.
