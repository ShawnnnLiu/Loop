# User Profile Schema

## Owner

Onboarding flow and profile service.

## Consumers

`StrategistNode`, validation layer, Scheduler, drift classifier.

## Purpose

Convert a vague career objective into machine-readable constraints. The profile is the source of truth for planning and scheduling. It must be a typed object, not a chat transcript.

## JSON Example

```json
{
  "user_id": "user_123",
  "profile_version": "profile_001",
  "goal": "Backend SWE interview prep",
  "target_role": "Backend SWE",
  "target_companies": ["Meta", "Stripe"],
  "target_level": "new_grad",
  "timeline_weeks": 10,
  "weekly_hours": 8,
  "experience_level": "intermediate",
  "known_strengths": ["arrays", "hash maps"],
  "known_weaknesses": ["dynamic programming", "system design"],
  "experience": [
    {
      "title": "Senior Backend Engineer",
      "organization": "Acme Corp",
      "summary": "Led the billing platform team; Python and Go services.",
      "kind": "work",
      "theme_tags": ["distributed-systems"]
    }
  ],
  "pathway_selection": {
    "pathway_id": "ai-integration-engineer",
    "pathway_registry_version": "pathway-registry-v1",
    "selected_at": "2026-07-19T12:00:00-07:00",
    "slot_overrides": []
  },
  "skills": ["Python", "Go", "PostgreSQL"],
  "preferred_session_length_min": 60,
  "max_session_length_min": 120,
  "deep_work_windows": [
    { "day": "Mon", "start": "18:00", "end": "21:00" },
    { "day": "Wed", "start": "19:00", "end": "21:30" }
  ],
  "hard_constraints": {
    "no_events_before": "08:00",
    "no_events_after": "22:30",
    "allow_weekends": true,
    "max_daily_study_min": 180,
    "min_break_between_deep_blocks_min": 30
  },
  "preferences": {
    "prefer_evening_sessions": true,
    "prefer_weekend_long_blocks": false,
    "avoid_back_to_back_deep_work": true
  },
  "motivation_profile_id": "mot_001",
  "resume_text": "Senior backend engineer, 4 yrs Python/Go. Led billing platform...",
  "plan_direction": "Blind 75 first, then two weeks of system design. Company research last.",
  "created_at": "2026-04-28T12:00:00-07:00",
  "updated_at": "2026-04-28T12:00:00-07:00"
}
```

## Required Fields

- `user_id`
- `profile_version`
- `goal`
- `target_role`
- `timeline_weeks`
- `weekly_hours`
- `experience_level`
- `preferred_session_length_min`
- `max_session_length_min`

## Field Semantics

| Field | Purpose |
| --- | --- |
| `goal` | Defines the high-level user objective |
| `target_role` | Guides curriculum and task categories |
| `target_companies` | Enables company-specific interview pattern retrieval. Company names **or company categories**: résumé extraction only ever proposes categories; users may add names manually |
| `target_level` | Changes depth and difficulty |
| `timeline_weeks` | Controls pacing and compression |
| `weekly_hours` | Caps workload |
| `experience_level` | Affects duration estimates and module difficulty |
| `known_strengths` | Can reduce emphasis on certain modules |
| `known_weaknesses` | Increases priority and review frequency |
| `experience` | The user's confirmed evidence inventory (`ExperienceItem` list, max 20, default empty; the field name predates the story layer and deliberately stays). Each entry carries a `kind` (closed enum, default `work`) and `theme_tags` (closed vocabulary, default empty). User-editable profile data; **not** consumed by Strategist/Planner prompts (see Prompt Exposure) |
| `pathway_selection` | Optional `PathwaySelection` (`pathway-selection.schema.md`). Absent = the user skipped the Your-story step and all downstream surfaces behave as today. Reaches the Strategist as typed constraints only (see Prompt Exposure) |
| `skills` | Tools/stack tokens (max 40, default empty), distinct from `known_strengths` (broader capabilities). Stored as display strings: extraction-matched skills are stored under their canonical taxonomy `display_name`, but the user may hand-type anything — the vocabulary constrains the LLM, not the person. Consumers needing canonical ids re-normalize at read time with the deterministic kernel |
| `preferred_session_length_min` | Helps generate realistic task durations |
| `max_session_length_min` | Prevents tasks too large for user sessions |
| `deep_work_windows` | Helps schedule high-cognitive-load tasks |
| `hard_constraints` | Defines non-negotiable scheduling boundaries |
| `preferences` | Soft constraints used when multiple schedules are valid |
| `motivation_profile_id` | Foreign key into `motivation_profiles`; drives accountability intensity, check-in cadence, and sponsor permissions |
| `resume_text` | Optional free text the user pastes during onboarding. Raw context with exactly two consumers: the `StrategistNode` (appended as a labeled raw block to sharpen the proposed syllabus) and the `ResumeIntakeNode` (input for extract→review→confirm). Never an oracle for routing or validation. Absent for users who skip the step. |
| `plan_direction` | Optional free text (max 4,000 chars, ~one page) the user pastes during onboarding or a profile edit: their own proposed plan, sequencing, or first steps toward the goal. Raw context with exactly **one** consumer: the `StrategistNode` (appended as a labeled raw block; the Strategist translates it into the syllabus, honoring the user's structure where constraints allow). Never an oracle for routing or validation. Absent when the user skips it. |

`resume_text` is **PII**: it is stored only on the user's own profile record, is not shared cross-user, and is deleted with the profile. It is sent to the LLM provider as prompt context by its two consumers (Strategist raw block; ResumeIntakeNode input — see `resume-intake-input.schema.md`), but is never persisted in the LLM call log (which records hashes and counts only — see `../axioms/22-llm-evaluation-and-observability.md`) and is never used for training. The extract→review→confirm parser is the `ResumeIntakeNode` (`../axioms/01-system-boundaries.md`, added 2026-07-06): it proposes candidates for the fields below; nothing it produces reaches this profile without the user confirming through `POST /api/onboard`.

`plan_direction` is user-authored untrusted input and may contain personal detail: stored only on the user's own profile record, not shared cross-user, deleted with the profile. It is sent to the LLM provider as prompt context by its single consumer (Strategist labeled raw block), is never persisted in the LLM call log (hashes and counts only — see `../axioms/22-llm-evaluation-and-observability.md`), and is never used for training. It never reaches the Planner, ResumeIntake, Reflection, or Explanation prompts, and no deterministic component (routing, validation, prerequisites, scheduling, confidence) reads it.

## Prompt Exposure (normative)

Which profile fields reach which LLM node's prompt. This table is the
source of truth; adapter code must match it (the Strategist bundle
exclusion set is asserted against this table in tests).

| Profile field | ResumeIntake | Strategist bundle | Planner |
| --- | --- | --- | --- |
| `experience` | output only | **excluded** (noise; the raw résumé block already covers background) | no |
| `skills` | output only | included | no |
| `known_strengths` / `known_weaknesses` | output only | included (coverage rule) | weaknesses only (unchanged) |
| `target_companies` | output only (categories) | included (unchanged) | no |
| `resume_text` | input (labeled raw block) | excluded from the structured bundle, appended as a labeled raw block (unchanged) | no |
| `plan_direction` | no | excluded from the structured bundle, appended as a labeled raw block | no |
| `experience[].kind` / `.theme_tags` | output only | **excluded** (rides `experience`, which never reaches the bundle) | no |
| `pathway_selection` | no | **excluded** - reaches the Strategist as typed constraints only (`pathway_id` + computed `unfilled_slots` in `StrategyConstraints`; never the selection object, never template prose) | no |

The Strategist bundle exclusion set is therefore `{"resume_text",
"experience", "plan_direction", "pathway_selection"}`.

Motivation, accountability, sponsor visibility, and pressure tolerance live in a separate `motivation_profile` object so they can change on a different cadence than planning constraints without invalidating the syllabus. See `motivation-profile.schema.md` and `../axioms/21-accountability-layer.md`.

## Validation Rules

- `user_id`, `profile_version`, `goal`, and `target_role` must be non-empty strings.
- `weekly_hours` must be `> 0` and `<= 40`.
- `timeline_weeks` must be `> 0`.
- `max_session_length_min` must be `>= preferred_session_length_min`.
- `hard_constraints.no_events_before` must be earlier than `hard_constraints.no_events_after`.
- `experience_level` must be one of `beginner`, `intermediate`, `advanced`.
- `experience` holds at most 20 `ExperienceItem` entries: `title` required
  (1–120 chars), `organization` optional (max 120 chars), `summary` optional
  (max 280 chars), `kind` one of `work · project · volunteering · leadership ·
  research · award · coursework` (default `work`), `theme_tags` at most 5
  entries (each 1–60 chars, case-insensitively unique; membership in the
  registry theme vocabulary is a service-layer check, not a contract-shape
  check - the vocabulary constrains the LLM proposal, and the UI offers the
  same closed dropdowns).
- `pathway_selection`, when present, is a valid `PathwaySelection`
  (`pathway-selection.schema.md`).
- `skills` holds at most 40 non-empty strings (each max 60 chars),
  case-insensitively unique.
- `plan_direction`, when present, is 1–4,000 characters and contains no
  C0 control characters other than `\n`, `\r`, `\t`.
- `deep_work_windows[*].day` must be a recognized day-of-week token.
- `deep_work_windows[*]` start must be before end and within allowed hours.
- All times use the user's timezone in HH:MM (24-hour) format.
- Profile changes must produce a new `profile_version` and update `updated_at`.

## Profile Update Policy

| Profile Change | Invalidate Syllabus? | Invalidate Tasks? | Invalidate Schedule? | Invalidate Accountability Contract? |
| --- | --- | --- | --- | --- |
| Weekly hours changed | No | Maybe | Yes | Maybe |
| Target role changed | Yes | Yes | Yes | Maybe |
| Target company added | Maybe | Maybe | Maybe | No |
| Availability changed | No | No | Yes | No |
| Weakness added | Yes | Yes | Yes | No |
| Preferred session length changed | No | Maybe | Yes | No |
| Self-motivation level changed | No | No | No | Maybe |
| Sponsor visibility changed | No | No | No | Yes |
| Pressure tolerance changed | No | No | No | Maybe |
| Weekly check-in disabled | No | No | No | Yes |
| Plan direction changed | No | No | No | No |
| Pathway selected or changed | Yes | Yes | Yes | No |
| Evidence item added/edited/marked | No | No | No | No |

Changing `plan_direction` invalidates nothing by itself: it shapes the *next*
fresh propose only (a rebuild goes through re-onboard → fresh propose; replans
never re-run the Strategist and are unaffected by design).

Evidence changes recompute slot coverage on read - they never invalidate plans
by themselves (a filled slot makes a planned module *redundant*, which the
next regular replan absorbs; auto-replan on evidence change is exactly the
autonomous replanning the MVP excludes).

See `../axioms/12-edge-case-policy-engine.md` and `../axioms/21-accountability-layer.md`.

## Invalid Examples

```json
{ "weekly_hours": 0, "timeline_weeks": 10 }
```

Reason: zero capacity.

```json
{
  "preferred_session_length_min": 90,
  "max_session_length_min": 60
}
```

Reason: max less than preferred.

```json
{
  "hard_constraints": {
    "no_events_before": "22:00",
    "no_events_after": "18:00"
  }
}
```

Reason: no_events_before is after no_events_after.

```json
{ "experience_level": "expert" }
```

Reason: invalid enum.

## Related Docs

- `../axioms/03-data-contracts.md`
- `../axioms/05-scheduler-policy.md`
- `../axioms/12-edge-case-policy-engine.md`
- `../axioms/21-accountability-layer.md`
- `motivation-profile.schema.md`
- `pathway-selection.schema.md`
- `pathway-template.schema.md`
- `resume-extraction.schema.md`
- `resume-intake-input.schema.md`
- `skill-taxonomy.schema.md`
