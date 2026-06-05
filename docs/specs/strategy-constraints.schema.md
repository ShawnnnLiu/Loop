# Strategy Constraints Schema

## Owner

The Strategist composition root (Phase 5b); part of the `StrategistInput` bundle.

## Consumers

`StrategistNode` (must respect these bounds when proposing a syllabus) and the
deterministic output gate in `llm_nodes/strategist.py` (which *disposes*:
rejects/repairs an out-of-bounds proposal).

## Purpose

The deterministic bounds a Strategist proposal must satisfy. The Strategist
*proposes* modules; these constraints are part of what the deterministic layer
uses to gate the output. All fields have spec defaults, so `{}` is valid.

## JSON Example

```json
{
  "max_modules": 12,
  "required_priority_values": ["high", "medium", "low"],
  "max_total_estimated_minutes": 4800,
  "must_reference_claims_for_company_specific_modules": true
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `max_modules` | Upper bound on syllabus module count (`> 0`, `<= 100`; default 12) |
| `required_priority_values` | Allowed `Priority` values, non-empty and unique (default `[high, medium, low]`) |
| `max_total_estimated_minutes` | Upper bound on summed module minutes (`> 0`; default 4800) |
| `must_reference_claims_for_company_specific_modules` | When true, a `company_specific` module must cite >= 1 `source_claim_id` (default true) |

## Invariants

- `required_priority_values` is non-empty and contains no duplicates.
- `max_modules` in `(0, 100]`; `max_total_estimated_minutes > 0`.
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "required_priority_values": [] }
```

Reason: `required_priority_values` must be non-empty.

```json
{ "required_priority_values": ["high", "high"] }
```

Reason: duplicate priority values.

## Related Docs

- `syllabus-units.schema.md` ("Strategist Inputs")
- `strategist-input.schema.md`
- `../axioms/04-validation-layer.md`
