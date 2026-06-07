# Milestone Template Schema

## Owner

The deterministic `templates/` registry (Phase 5c skeleton seed layer).

## Consumers

Syllabus seeding (a template expands into `SyllabusModule`s), the `task_template`
cache target (axiom 18), and operator views (`tools/list_templates.py`).

## Purpose

A `MilestoneTemplate` is a deterministic *seed* for a `goal_class`: a small,
ordered set of `Milestone`s that a later stage expands into syllabus modules.
Templates are canned, validated literals owned by the registry — the single
source of truth for which goal class maps to which template. LLMs do not author
templates; this is deterministic infrastructure.

## JSON Example

```json
{
  "template_id": "career-transition-skeleton",
  "goal_class": "career_transition",
  "template_schema_version": "milestone-template-v1",
  "milestones": [
    {
      "milestone_id": "skill-gap-assessment",
      "title": "Skill-gap assessment",
      "offset_days_before_deadline": 120,
      "target_outcomes": ["Target-role skill gaps identified"],
      "priority": "high",
      "default_estimated_total_min": 600
    },
    {
      "milestone_id": "interview-preparation",
      "title": "Interview preparation",
      "offset_days_before_deadline": 14,
      "target_outcomes": ["Mock interviews completed"],
      "priority": "high",
      "default_estimated_total_min": 1800
    }
  ]
}
```

## Field Semantics

### `MilestoneTemplate`

| Field | Purpose |
| --- | --- |
| `template_id` | Stable identifier for the template |
| `goal_class` | The goal class this template seeds (see below) |
| `template_schema_version` | Shape version; feeds `CacheKey.object_schema_version` for the `task_template` cache target (axiom 18) |
| `milestones` | Ordered, non-empty list of `Milestone`s with unique `milestone_id`s |

### `Milestone`

| Field | Purpose |
| --- | --- |
| `milestone_id` | Stable identifier, unique within a template |
| `title` | Human-readable milestone title |
| `offset_days_before_deadline` | Days before the goal deadline this milestone anchors to (`>= 0`) |
| `target_outcomes` | Non-empty list of concrete outcomes (same shape as `SyllabusModule.target_outcomes`) |
| `priority` | `high`, `medium`, or `low` (shared `Priority`) |
| `default_estimated_total_min` | Seed estimate in minutes (`> 0`) |

## Allowed `goal_class` Values

- `college_admissions`
- `graduate_admissions`
- `career_transition`

Every `goal_class` has exactly one registered template; registry completeness is
tested (`tests/templates/test_registry.py`).

## Contract vs. Registry Responsibility

The Pydantic contract
(`backend/src/agentic_calendar/contracts/milestone_template.py`) enforces only
**shape and internal consistency**: field types and bounds, a non-empty
`milestones` list, and unique `milestone_id`s. The *content* of the templates —
which milestones a goal class gets — lives in the `templates/` registry as
validated literals, the single sanctioned source. There is no `docs/specs` JSON
schema beyond this document and the generated `schemas/milestone_template.schema.json`.

## Invariants

- `milestones` is non-empty.
- `milestone_id` values are unique within a template.
- `offset_days_before_deadline >= 0`; `default_estimated_total_min > 0`; `target_outcomes` is non-empty.
- `goal_class` must be a known value from the list above.
- Templates are deterministic literals; an LLM never produces one.

## Invalid Examples

```json
{ "template_id": "t", "goal_class": "career_transition", "template_schema_version": "v1", "milestones": [] }
```

Reason: `milestones` must be non-empty.

```json
{
  "template_id": "t",
  "goal_class": "career_transition",
  "template_schema_version": "v1",
  "milestones": [
    { "milestone_id": "dup", "title": "A", "offset_days_before_deadline": 30, "target_outcomes": ["x"], "priority": "high", "default_estimated_total_min": 60 },
    { "milestone_id": "dup", "title": "B", "offset_days_before_deadline": 10, "target_outcomes": ["y"], "priority": "low", "default_estimated_total_min": 60 }
  ]
}
```

Reason: duplicate `milestone_id`.

## Related Docs

- `../axioms/18-caching-strategy.md`
- `../axioms/10-mvp-roadmap.md`
- `syllabus-units.schema.md`
