# SPEC · Onboarding

First-run setup. A **linear 7-step wizard**. Deterministic everywhere except two file-parse steps. Resumable at any step (the topbar shows "Save & exit"; refresh resumes at `currentStep` with prior answers intact). Footer on every screen: "Every answer is editable later in **Settings**" — so onboarding writes to the same profile store Settings reads.

Reference component: `reference/onboarding.jsx` → screens render in `reference/preview.html` (section 01). Source-of-truth data shapes are in `DATA-MODEL.md` (`OnboardingState`, `AcademicProfile`, `Course`, `ApplicantProfile`).

## Step sequence

| # | Step (rail label) | Mode | Collects |
|---|---|---|---|
| 1 | Goal | deterministic | objective / target outcome |
| 2 | Hours | deterministic | hours available per week (2–25) |
| 3 | **Deadline** | deterministic | target date → derived runway weeks |
| 4 | **Transcript** | **AI parse** | upload transcript → GPA, course history, rigor, trajectory |
| 5 | **Courses** | deterministic | current-term courses + expected grades + focus |
| 6 | **Activities** | **AI parse** | upload activities/résumé → profile, activities, strengths |
| 7 | Connect | deterministic | Google Calendar connect |

The step rail (left, in `OnbDeadline`) shows all 7 with done (✓) / active / upcoming states. The four reference screens are steps 3, 4, 5, 6 — the most representative; steps 1, 2, 7 follow the same deterministic form pattern.

## Shared chrome
- **Topbar** (`Topbar`): brand mark (同 glyph with clay ✓ badge) · "First-run setup" label · "Save & exit".
- **Stepper** (`Stepper`): "Step N / 7" + a 7-segment fill track.
- **Engine badge** (`Engine`): a pill that reads **"Deterministic step" (D)** or **"AI-assisted step" (AI)**. This badge is non-negotiable on every screen — it's how the user always knows whether a model is involved.
- **Footer bar**: progress + est. time on the left; the "editable later" / next-step note on the right.

## Screen 3 · Deadline (deterministic)
3-column feel: step rail (left) · main column · the rail also carries a **"Why a plain form?"** explainer card listing the three things AI *is* used for ("read your transcript / read your activities / draft your plan"). Keep this reassurance — it sets up the trust model.
- Main: Engine=D badge, H1 "When's your deadline?", helper copy, then a **2×2 grid of runway cards** (Soon · In 4 weeks / **Balanced · In 12 weeks** [selected] / Long runway · In 6 months / Custom · pick a date [dashed]).
- Below: a summary strip showing **Target date** + **Runway** (`~12 weeks`, clay) — runway is **derived** from the date, not asked.
- Nav: ← Back / "press ↵" / **Next: Transcript →**.

## Screen 4 · Transcript parse (AI) — one of the two model steps
Two columns: **upload (left)** · **extracted review (right)**.
- Left: Engine=AI badge, H1 "Drop your transcript in", helper "AI reads it — you confirm every number", a **dropzone** (official/unofficial PDF; Browse files / Enter grades by hand), an **uploaded-file row** (filename · size · "parsed in 1.9s" · "✓ read" · Remove), and a **privacy guard** line (🔒 grades private, never used for training, deletable).
- Right (raised card): eyebrow "Extracted from your transcript" + **"AI · please review"** chip, H2 "Do these grades look right?", "nothing is saved until you confirm". Fields:
  - **GPA stats** — Unweighted 3.8/4.0, Weighted 4.12/5.0, Class rank ("School doesn't rank").
  - **Course history** — chips grouped by grade year (some highlighted "on"); editable.
  - **Rigor** (2 Honors · 0 AP) + **Trajectory** (sage box, "Trending up ↗ 3.6 → 3.9").
  - **Inferred** (clay flag box, "a guess") — the tier-2 hypothesis; explicitly not a fact.
- Actions: ← Back · **Looks wrong, redo** (re-runs parse) · **Confirm & continue →** (commits to `AcademicProfile`).

## Screen 5 · Current courses & grades (deterministic)
- Engine=D badge, H1 "Your courses this term", helper "We pulled this term from your transcript — no AI here."
- A **table**: Course / Level (AP·Honors·CP chips) / **Expected grade** (user-set) / **Focus** (strong · okay · **needs work** in clay). "+ add a course" (dashed chip).
- Summary row: course count · 1 AP · **Projected term GPA 3.7** + a clay flag "We'll protect time for [the needs-work courses]". `focus: needs work` → time protection downstream.

## Screen 6 · Activities parse (AI) — the second model step
Mirror of screen 4. Left = upload (PDF/DOCX/TXT; Browse / Paste Common App activities). Right = review card "Extracted from your resume" + "AI · please review":
- **Profile** — grade/class year + chips (entry term, decision plan, intended major).
- **Activities & leadership** — chips + "+ add".
- **Personal projects** — **gold "required" box**; flags when thin ("Add one self-started project… a clear 'spike' stands out most").
- **Strengths** — sage auto-detected theme tags.
- **Inferred weak spots** — clay flag, "a guess" (few APs / no clear spike / member not officer / essays not started).
- Actions: ← Back · Looks wrong, redo · Confirm & continue → (commits to `ApplicantProfile`).

## Behavior to implement
- Linear next/back; progress reflects `currentStep`; Save & exit persists and resumes.
- **Steps 4 and 6 are the only async steps** (upload → parse → review → confirm). All others are synchronous form submits with no model call.
- Both parse steps are **skippable** → fall back to manual entry, no model call.
- "Looks wrong, redo" = re-invoke the parse on the same file (new `Proposal`).
- Nothing parsed is persisted to the profile until **Confirm & continue** — until then it's a pending `Proposal`.
- Inferred notes (screens 4 & 6) carry forward as **editable defaults** into planning, never as locked truth.
