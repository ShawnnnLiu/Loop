# Threshold Change Log Schema

## Owner

The tuning loader (`backend/src/agentic_calendar/app/tuning.py`). Axiom 07
("Threshold Change Log", `../axioms/07-telemetry-and-drift.md`) requires every
threshold modification to be recorded; the loader is the only supported path
for changing a tuning value and writes exactly one entry per effective change.

## Consumers

`show_thresholds` operator CLI (effective-value replay and history view),
calibration reviews (axiom 07 "Calibration Roadmap"), engineering review.

## Purpose

`ThresholdChange` is the append-only audit record for one modification of one
deterministic tuning knob. Axiom 07 defines `drift_threshold_history` for the
drift classifier's thresholds; this contract generalizes that journal to
**every** deterministic tuning knob that lives in a config dataclass — drift
thresholds, calibration parameters, pooled-estimator training and serving
parameters, and power-user eligibility/refinement parameters.

The log is audit, never control plane: runtime classification reads the
*effective config instance*, which the loader builds deterministically from
defaults plus the journaled overrides. No routing decision reads this log.

All recorded values are heuristic priors until calibration completes (axiom 07
"MVP Disclosure"); the journal is what makes a future calibrated change
auditable against the priors it replaced.

### Scope

The section vocabulary (which `config_section` values exist and which fields
each section owns) is owned by the tuning registry in
`app/tuning.py` (`TUNABLE_SECTIONS`). The contract validates **shape only**
(`^[a-z][a-z0-9_]*$`); semantic validation against the registry happens in the
loader before an entry is ever constructed. Current registry sections:

- `drift_thresholds` (`drift/thresholds.py`, `DriftThresholds`)
- `calibration` (`telemetry/calibration.py`, `CalibrationConfig`)
- `pooled_training` (`duration_estimation/pooled.py`, `PooledTrainingConfig`)
- `pooled_serving` (`duration_estimation/pooled.py`, `PooledServingConfig`)
- `power_user_eligibility` (`duration_estimation/power_user.py`, `EligibilityConfig`)
- `per_user_refinement` (`duration_estimation/power_user.py`, `RefinementConfig`)

Only scalar (`int` / `float`) dataclass fields are tunable. Structured fields
(e.g. `calibration.quality_weights`, a mapping) are not overridable through
this mechanism. Knobs that still live as module constants (e.g. the
accountability policy floors) are honestly **out of scope** until they become
config dataclass fields — they cannot be journaled, so they cannot be tuned
through the supported path.

## JSON Example

```json
{
  "change_id": "thrchg_001",
  "config_section": "drift_thresholds",
  "threshold_field": "duration_underestimate_ratio",
  "prior_value": 1.3,
  "new_value": 1.4,
  "effective_at": "2026-06-11T09:00:00-07:00",
  "justification": "Underestimate drift fired weekly on a working plan; one notch looser cuts the false positives observed in dogfooding.",
  "dataset_reference": "telemetry through 2026-06-10"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `change_id` | string | Primary key; unique, used for append-only dedup. |
| `config_section` | string, `^[a-z][a-z0-9_]*$` | Which config dataclass the change targets. Vocabulary owned by the tuning registry, not by this contract. |
| `threshold_field` | string, `^[a-z][a-z0-9_]*$` | The scalar field within the section. Must exist on the registered dataclass (loader-enforced). |
| `prior_value` | number (int or float, strict) | The effective value being replaced: the default, or the last journaled `new_value` for this `(config_section, threshold_field)`. |
| `new_value` | number (int or float, strict) | The value now in effect. Must differ from `prior_value` — a no-op is not a change and must not be journaled. |
| `effective_at` | datetime | When the change took effect. Timezone-aware. |
| `justification` | string, 1–500 chars | Why the value moved. Bounded prose for human audit only — never control-plane input. |
| `dataset_reference` | string, 1–200 chars | What data motivated the change (e.g. `"telemetry through 2026-06-10"`, `"manual prior"`). |

Booleans are **not** numbers here: the contract uses strict number types, so
`true` / `false` are rejected for `prior_value` / `new_value`.

## Required Fields

All eight fields are required. There are no defaults.

## Validation Rules

- `effective_at` must be timezone-aware.
- `new_value` must differ from `prior_value` (numeric comparison: `1` and
  `1.0` are the same value).
- `prior_value` / `new_value` accept strict int or strict float only; boolean
  values are rejected.
- `justification` is 1–500 characters; `dataset_reference` is 1–200.
- `config_section` / `threshold_field` match `^[a-z][a-z0-9_]*$`.
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "prior_value": 1.3, "new_value": 1.3 }
```

Reason: a no-op is not a change; journaling it would fake an audit trail.

```json
{ "effective_at": "2026-06-11T09:00:00" }
```

Reason: naive datetimes are ambiguous audit facts.

```json
{ "new_value": true }
```

Reason: booleans are not tunable numbers; strict types reject them.

```json
{ "justification": "" }
```

Reason: axiom 07 requires every change to carry a justification.

## Append-Only Store Semantics

`ThresholdChangeLogStore` (`app/threshold_log.py`, in-memory and SQLite
twins): a `change_id` may be written exactly once; entries are immutable audit
facts, never edited. Reads are `list_all()` and
`list_for_field(config_section, threshold_field)`, both in insertion order —
the latest entry for a field is its effective override, so deterministic
replay of the list reproduces the effective configuration.

The loader (`app/tuning.py`) is the only supported mutation path: applying a
`tuning.toml` override that changes an effective value always appends an
entry, and re-applying the same file appends nothing (idempotent re-load).
**No silent threshold changes** — a tuning value that differs from its default
without a journal entry is a bug.

Reversions are journaled too: applying a file that no longer carries a
previously journaled override — or applying with no tuning file at all —
appends a reversion entry per such field, with `prior_value` = the replayed
journal value and `new_value` = the code default now back in effect. The
file's top-level `justification` / `dataset_reference` are reused when
present; otherwise the loader's `REVERSION_JUSTIFICATION` /
`REVERSION_DATASET_REFERENCE` constants fill the record (`dataset_reference`
is `"tuning file absent"` when no file was supplied). This too is idempotent:
once the reversion is journaled, the replayed value equals the default and
the next apply appends nothing — so reverting to a default is never a silent
change either.

## Related Docs

- `../axioms/07-telemetry-and-drift.md` (Threshold Change Log, MVP Disclosure)
- `../implementation-plans/phase-9-dogfood-backbone.md`
- `llm-call-log.schema.md` (the sibling append-only audit log pattern)
