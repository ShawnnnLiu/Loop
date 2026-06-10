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
| `target_companies` | Enables company-specific interview pattern retrieval |
| `target_level` | Changes depth and difficulty |
| `timeline_weeks` | Controls pacing and compression |
| `weekly_hours` | Caps workload |
| `experience_level` | Affects duration estimates and module difficulty |
| `known_strengths` | Can reduce emphasis on certain modules |
| `known_weaknesses` | Increases priority and review frequency |
| `preferred_session_length_min` | Helps generate realistic task durations |
| `max_session_length_min` | Prevents tasks too large for user sessions |
| `deep_work_windows` | Helps schedule high-cognitive-load tasks |
| `hard_constraints` | Defines non-negotiable scheduling boundaries |
| `preferences` | Soft constraints used when multiple schedules are valid |
| `motivation_profile_id` | Foreign key into `motivation_profiles`; drives accountability intensity, check-in cadence, and sponsor permissions |

Motivation, accountability, sponsor visibility, and pressure tolerance live in a separate `motivation_profile` object so they can change on a different cadence than planning constraints without invalidating the syllabus. See `motivation-profile.schema.md` and `../axioms/21-accountability-layer.md`.

## Validation Rules

- `user_id`, `profile_version`, `goal`, and `target_role` must be non-empty strings.
- `weekly_hours` must be `> 0` and `<= 40`.
- `timeline_weeks` must be `> 0`.
- `max_session_length_min` must be `>= preferred_session_length_min`.
- `hard_constraints.no_events_before` must be earlier than `hard_constraints.no_events_after`.
- `experience_level` must be one of `beginner`, `intermediate`, `advanced`.
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
