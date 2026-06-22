# Data Model & API Contract

The backend spec. Everything in the three flows renders off these entities. Types are illustrative (TypeScript-ish); map to your ORM/language. IDs are opaque strings.

---

## 1. Core principle encoded as data: the Proposal gate

Anything the model generates becomes a **`Proposal`**, never a direct write. A proposal is the only thing the approval UI acts on. Accepting a proposal is what triggers a deterministic side effect (e.g. a Google Calendar write). This single indirection is what makes rule #1 ("no model output causes a side effect without an explicit ✓") true at the data layer.

```
model call ──► Proposal{status:'pending'} ──► user ✓ ──► deterministic apply() ──► side effect + status:'accepted'
                                          └─► user ✕ ──► status:'rejected' (no side effect)
```

---

## 2. Entities

### User
```ts
User {
  id, name, email,
  gradeLevel: number,            // e.g. 11
  classYear: number,             // e.g. 2027
  intendedMajor?: string,        // "Biology (Pre-med)"
  createdAt, updatedAt
}
```

### OnboardingState
One per user; a resumable draft that **upserts into the real profile** as steps complete (onboarding and Settings write the same records — nothing here is write-once).
```ts
OnboardingState {
  userId,
  currentStep: 1..7,
  completedSteps: number[],
  // step 1–3 (deterministic):
  goal?: string,                 // objective / target outcome
  hoursPerWeek?: number,         // 2..25
  deadline?: {                   // step 3
    date: ISODate,               // "2026-11-01"
    track: 'soon'|'balanced'|'long'|'custom',
    runwayWeeks: number          // DERIVED from date − today; never stored as input
  },
  // step 4 (AI parse → review):  see Transcript / Proposal
  transcriptUploadId?: string,
  academics?: AcademicProfile,   // confirmed copy of the parsed result
  // step 5 (deterministic):
  currentCourses?: Course[],
  // step 6 (AI parse → review):
  activitiesUploadId?: string,
  applicantProfile?: ApplicantProfile,
  // step 7 (deterministic):
  calendar?: { connected: boolean, provider: 'google' }
}
```

### AcademicProfile  (output of the step-4 transcript parse, after user confirmation)
```ts
AcademicProfile {
  gpaUnweighted: number,         // 3.8
  gpaWeighted: number,           // 4.12
  gpaScaleWeighted: number,      // 5.0
  classRank?: string|null,       // "School doesn't rank"
  courseHistory: {               // grouped by year
    grade: number, courses: { name, grade }[]
  }[],
  rigor: { honorsCompleted: number, apCompleted: number },
  trajectory?: string,           // "Trending up ↗ 3.6 → 3.9" (display string; store the deltas too if you can)
  inferred?: InferredNote        // tier-2 guess, see §3
}
```

### Course  (step 5, deterministic — current term)
```ts
Course {
  id, name,                      // "AP Biology"
  level: 'AP'|'Honors'|'CP',
  expectedGrade: string,         // "A−"  (user-set, honest self-estimate)
  focus: 'strong'|'okay'|'needs work',  // drives time protection
  source: 'transcript'|'user'    // pulled vs hand-added
}
// derived: courseCount, apCount, projectedTermGpa, protectedCourses[] (focus==='needs work')
```

### ApplicantProfile  (output of the step-6 activities parse, after confirmation)
```ts
ApplicantProfile {
  entryTerm: string,             // "Fall 2027"
  decisionPlan: 'ED'|'EA'|'RD'|'Rolling',
  intendedMajor: string,
  activities: { name, role?, hours?: number }[],
  personalProjects: { name, detail?: string }[],   // UI flags this REQUIRED if thin
  strengths: string[],           // auto-detected theme tags: "STEM curiosity", "Service-minded"
  inferredWeakSpots?: InferredNote  // tier-2 guess: "few APs", "no clear spike yet", ...
}
```

### Milestone  (the application backbone — drives the calendar milestone track)
```ts
Milestone {
  id, userId,
  label: string,                 // "Personal essay"
  order: number,
  state: 'done'|'active'|'todo',
  progress?: number,             // 0..1 for the active one (essay · 60%)
  targetDate?: ISODate
}
// the program has a target: { date, decisionPlan:'EA', runwayWeeks }
```

### Task / Block  (the atomic unit of the calendar + rail + approvals)
```ts
Block {
  id, userId,
  title: string,                 // "Personal essay · draft 1"
  date: ISODate,
  start?: time, end?: time,      // a locked block always has these (from gcal)
  durationPlannedMin?: number,
  durationActualMin?: number,    // set on mark-done
  milestoneId?: string,
  state: BlockState,             // see state machine below
  source: 'tandem'|'gcal',       // 'gcal' = locked external event (café shift)
  gcalEventId?: string,          // set once written to Google Calendar
  why?: string,                  // model's natural-language rationale (proposed/accepted blocks)
  proposalId?: string            // set while state==='proposed'
}
```

### Proposal  (the gate; wraps anything the model wants to do)
```ts
Proposal {
  id, userId,
  kind: 'parse'|'syllabus'|'block'|'week_regen'|'recovery'|'explain'|'reflection',
  payload: object,               // e.g. the drafted Block(s), or parsed fields
  status: 'pending'|'accepted'|'rejected'|'expired',
  createdAt,
  modelMeta: { model, tokens, latencyMs, costUsd },  // for cost caps + the "parsed in 1.9s" UI
  undoDeadline?: timestamp       // accept sets now()+60s; until then, revert is one click
}
```

### FileUpload
```ts
FileUpload {
  id, userId,
  kind: 'transcript'|'activities',
  filename, sizeBytes, mime,     // pdf/docx/txt
  storageRef,                    // user-scoped, private bucket
  parsedProposalId?: string,
  trainingOptOut: true,          // ALWAYS true — never used for training
  createdAt
}
```

### CalendarLink
```ts
CalendarLink {
  userId, provider:'google',
  accessToken, refreshToken, scopes,
  lastSyncAt, syncStatus: 'ok'|'stale'|'error'  // drives "synced 2m ago" pill
}
```

---

## 3. Confidence tiers (parsed output must carry this — it drives distinct UI)

The parse screens render three trust levels differently. Your parse response must tag fields so the UI can too:

1. **Extracted fact** — pulled from the document (GPA, course grades, activities). Shown plainly, editable.
2. **Inferred guess** (`InferredNote`) — a hypothesis, rendered in the **clay/coral flag box** labelled "a guess". Examples: transcript step → "course rigor is your biggest lever"; activities step → weak-spots chips ("few APs", "no clear spike yet"). **Explicitly not a fact.** It seeds later planning but is never locked truth.
3. **Auto-suggested / auto-detected** — convenience defaults (strength theme tags, decision plan). Freely editable.

```ts
InferredNote { text: string, tier: 'inferred', confidence?: number }
```

---

## 4. Block state machine (the heart of the UI)

```
        (model drafts)              user ✓                 user marks done
  ∅ ──────────────────► proposed ───────────► accepted ───────────────────► done
                           │  └── user ✕ ──► (deleted)        │
                           │                                  └── within 60s ── undo ──► proposed
  gcal import ──► locked  (external, immovable: café shift; never mutated by Tandem)
  rest-day rule ──► rest  (deterministic; no work scheduled)
```

| State | Meaning | Visual (see DESIGN-SYSTEM) | Who sets it |
|---|---|---|---|
| `proposed` | model-drafted, awaiting approval | **dashed clay** outline | AI (via Proposal) |
| `accepted` | approved → written to gcal | solid white card / clay tint | deterministic apply() on ✓ |
| `done` | completed, duration logged | ink fill / struck / "logged ✓" | deterministic on mark-done |
| `locked` | external gcal event, immovable | muted, 🔒 / "gcal" chip | calendar sync |
| `rest` | protected rest day | faint, italic | rest-day rule |

Transitions `proposed→accepted` and `accepted→done` are the **only** ones with side effects (gcal write; telemetry log). Both are deterministic and must be **idempotent + retry-safe**.

---

## 5. API contract (REST sketch — adapt to your conventions)

### Onboarding
```
GET  /onboarding                         → OnboardingState (resume where left off)
PATCH /onboarding/step/:n                 → save deterministic step slice; advance
POST /onboarding/upload                   → multipart {kind}; returns FileUpload
POST /uploads/:id/parse                   → runs the AI parse; returns Proposal{kind:'parse'}
POST /proposals/:id/accept                → commits parsed fields to AcademicProfile/ApplicantProfile
POST /proposals/:id/reject                → "looks wrong, redo" re-runs parse (new Proposal)
```

### Calendar / blocks
```
GET  /weeks/:isoWeek                       → { days: Day[], milestones: Milestone[], target }
POST /blocks/:id/accept                    → proposed→accepted; idempotent gcal write; returns undoDeadline
POST /blocks/:id/accept-all?day=:date      → batch ("Accept 2 proposed")
POST /blocks/:id/done                      → accepted→done; body {actualMin}; logs telemetry
POST /blocks/:id/undo                      → within 60s, revert last accept/done
POST /blocks/:id/reschedule                → deterministic move; respects busy + quiet hours
GET  /blocks/:id/why                       → AI explanation (kind:'explain'); read-only, no side effect
```

### Agent
```
GET  /agent/proposals?status=pending       → Proposal[] (the dock's approval list)
POST /agent/message                        → {text}; returns thread events incl. tool-call rows
POST /agent/commands/:cmd                  → /recover | /why | /regen-week | /explain → returns Proposal(s)
GET  /agent/thread                         → conversation + tool-call log (read_file rows, token counts)
```

### Calendar integration
```
POST /calendar/connect                     → Google OAuth start
GET  /calendar/status                      → CalendarLink.syncStatus + lastSyncAt ("synced 2m ago")
POST /calendar/sync                        → pull busy/locked windows
```

### Cross-cutting backend requirements
- **Idempotency:** `accept`/`done` keyed by block id + intended state — repeat calls don't double-write gcal or double-log.
- **Undo window:** persist `undoDeadline`; a background sweep finalizes after 60s. Until then `undo` reverts cleanly (delete the gcal event for an accept; restore prior state for a done).
- **Cost & concurrency caps:** per-user model budget + a concurrency lock so week-regen can't fan out into a runaway loop. Surface `modelMeta` (latency/tokens) — the UI shows "parsed in 1.9s".
- **Drift detection is deterministic:** `missedPct` + `rescheduleCount` over the week → `behind | on-track | ahead`. No model call. Feeds the rail's "on track" badge.
- **Quiet hours & locked events are never silently mutated** — the scheduler routes around them.
- **Derived values are computed, not stored as input:** `runwayWeeks`, `projectedTermGpa`, milestone `progress`, drift status.
