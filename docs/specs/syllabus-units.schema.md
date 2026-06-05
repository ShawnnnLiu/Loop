# Syllabus Units Schema

## Owner

`StrategistNode`, with deterministic validation before any consumer uses the output.

## Consumers

Validation layer, `PlannerNode`, coverage metrics, user-facing explanations.

## Purpose

Convert a `user_profile` and a set of `source_claim` objects into structured syllabus modules. Output must be a structured object, not prose. See `../decisions/ADR-0005-structured-syllabus-not-prose.md`.

## Strategist Inputs

```json
{
  "user_profile": { "...": "..." },
  "source_claims": [],
  "strategy_constraints": {
    "max_modules": 12,
    "required_priority_values": ["high", "medium", "low"],
    "max_total_estimated_minutes": 4800,
    "must_reference_claims_for_company_specific_modules": true
  }
}
```

## JSON Example

```json
{
  "syllabus_version": "syl_003",
  "goal_summary": "Prepare for backend SWE interviews at Meta and Stripe over 10 weeks.",
  "modules": [
    {
      "module_id": "dp",
      "title": "Dynamic Programming",
      "priority": "high",
      "reason": "User listed DP as a weakness and target companies commonly test algorithmic reasoning.",
      "target_outcomes": [
        "Recognize common DP state definitions",
        "Solve 1D and 2D DP problems under interview constraints"
      ],
      "estimated_total_min": 720,
      "difficulty": 5,
      "source_claim_ids": ["claim_012", "claim_018"]
    },
    {
      "module_id": "api_design",
      "title": "API Design and Product-Oriented Backend Design",
      "priority": "medium",
      "reason": "Relevant for Stripe-style backend interviews.",
      "target_outcomes": [
        "Design clean API surfaces",
        "Explain tradeoffs between consistency, latency, and developer experience"
      ],
      "estimated_total_min": 360,
      "difficulty": 4,
      "source_claim_ids": ["claim_024"]
    }
  ]
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `syllabus_version` | Stable identifier for this syllabus revision |
| `goal_summary` | Short user-facing summary of the goal interpretation |
| `modules[].module_id` | Stable identifier referenced by tasks |
| `modules[].title` | Display title |
| `modules[].priority` | `high`, `medium`, or `low` |
| `modules[].reason` | Why this module is included for this user |
| `modules[].target_outcomes` | Concrete outcomes the user must reach |
| `modules[].estimated_total_min` | Total estimated minutes for the module |
| `modules[].difficulty` | Integer in `1..5` |
| `modules[].source_claim_ids` | Claims that justify the module |
| `modules[].company_specific` | Whether the module is tailored to a specific target company (default `false`). The Strategist proposes it; the validator uses it to enforce the claim-reference rule below. |

## Validation Rules

- `module_id` values are unique.
- `priority` is `high`, `medium`, or `low`.
- `title` is required.
- `target_outcomes` is required and non-empty.
- High-priority modules must have a non-empty `reason`.
- `estimated_total_min` is a positive integer.
- `difficulty` is an integer in `[1, 5]`.
- `source_claim_ids` reference existing, non-expired `claim_id` values (checked in `validation/source_claims.py`; missing → `ORPHAN_SOURCE_CLAIM`, expired → `EXPIRED_SOURCE_CLAIM`).
- Total estimated time must not exceed user capacity by an impossible margin.
- A module with `company_specific: true` must reference at least one `source_claim_id` when `strategy_constraints.must_reference_claims_for_company_specific_modules` is true (else → `COMPANY_MODULE_MISSING_CLAIM`). "Company-specific" is the explicit `company_specific` flag, not inferred from prose.

## Syllabus Staleness Rules

A syllabus must be marked stale when:

- The user changes target role.
- The user changes target company set significantly.
- The user changes timeline significantly.
- The user adds or removes major weaknesses.
- Source claims expire.
- The drift classifier indicates curriculum-level mismatch.

A syllabus must not be regenerated just because the user misses a single task.

## Invalid Examples

```json
{
  "modules": [
    { "module_id": "dp", "module_id": "dp", "priority": "high" }
  ]
}
```

Reason: duplicate `module_id`.

```json
{
  "modules": [
    {
      "module_id": "dp",
      "priority": "urgent",
      "target_outcomes": []
    }
  ]
}
```

Reason: invalid priority and empty outcomes.

```json
{
  "modules": [
    {
      "module_id": "dp",
      "title": "Dynamic Programming",
      "priority": "high",
      "estimated_total_min": -120,
      "difficulty": 7
    }
  ]
}
```

Reason: invalid duration and out-of-range difficulty.

```json
{
  "modules": [
    {
      "module_id": "dp",
      "priority": "high",
      "title": "Dynamic Programming",
      "target_outcomes": ["Solve DP problems"],
      "source_claim_ids": ["claim_does_not_exist"]
    }
  ]
}
```

Reason: orphan source claim reference.

## Related Docs

- `../axioms/04-validation-layer.md`
- `../axioms/08-rag-source-claims.md`
- `../axioms/12-edge-case-policy-engine.md`
- `source-claim.schema.md`
- `../decisions/ADR-0005-structured-syllabus-not-prose.md`
