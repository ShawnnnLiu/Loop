# Schemas

Generated JSON Schema (draft 2020-12) for every Phase 1 Pydantic contract.
**Do not hand-edit.** Files here are produced by:

```bash
cd backend
make schemas
```

which runs `python -m agentic_calendar.tools.export_schemas --out ../schemas`.

## Why these are committed

These schemas are the cross-language contract surface for the project. The
backend produces them; the frontend (Phase 2+) and any non-Python consumers
(future TS clients, validators in CI, external API consumers) read them.
Committing the generated files means every PR that changes a contract
produces a reviewable diff, and any drift between the Pydantic models and
the JSON Schema is caught by CI:

```bash
cd backend
uv run python -m agentic_calendar.tools.export_schemas --check --out ../schemas
```

## Files

| File | Source model |
| --- | --- |
| `user_profile.schema.json` | `agentic_calendar.contracts.user_profile.UserProfile` |
| `motivation_profile.schema.json` | `agentic_calendar.contracts.motivation_profile.MotivationProfile` |
| `syllabus_units.schema.json` | `agentic_calendar.contracts.syllabus_units.SyllabusUnits` |
| `task_plan.schema.json` | `agentic_calendar.contracts.task_plan.TaskPlan` |
| `validation_result.schema.json` | `agentic_calendar.contracts.validation_result.ValidationResult` |
| `scheduler_output.schema.json` | `agentic_calendar.contracts.scheduler_output.SchedulerOutput` |

The canonical prose specs that govern these schemas live under
[`../docs/specs/`](../docs/specs/). Always update the spec first, then the
Pydantic model, then run `make schemas`.
