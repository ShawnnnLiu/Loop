# Pathway Selection Schema

## Owner

Onboarding flow and profile service.
Stored on the user profile only via the existing confirm gate (`POST /api/onboard` at onboarding; the profile-update path from Tuning thereafter).

## Consumers

The `narrative/` kernel (coverage/fit/progress against the pinned registry version), the Strategist constraints composition root (projects `pathway_id` + computed `unfilled_slots` into `StrategyConstraints`), and the onboarding/Tuning UI.

## Purpose

`PathwaySelection` is the user's explicit choice of one pathway - typed control-plane state.
No pathway is active until the user picks one; skipping stores nothing and every downstream surface behaves exactly as today.
Selection is an explicit user gate: it reaches the Strategist only as structured constraint extensions, never as prose.

## JSON Example

```json
{
  "pathway_id": "ai-integration-engineer",
  "pathway_registry_version": "pathway-registry-v1",
  "selected_at": "2026-07-19T12:00:00-07:00",
  "slot_overrides": [
    {
      "item_title": "Senior Backend Engineer",
      "item_organization": "Acme Corp",
      "slot_id": "llm-feature-depth"
    }
  ]
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `pathway_id` | The chosen pathway; must be a member of the registry (checked deterministically at the service layer, `UNKNOWN_PATHWAY_ID` on failure) |
| `pathway_registry_version` | Pins which registry version the selection was made against (taxonomy-version discipline) |
| `selected_at` | Timezone-aware timestamp of the confirm |
| `slot_overrides` | Optional explicit item-to-slot assignments where the user corrected the kernel's deterministic greedy mapping |

`SlotOverride` identifies an evidence item by the same identity the profile uses for `experience` entries - the case-insensitive `(title, organization)` pair:

| Field | Purpose |
| --- | --- |
| `item_title` | `ExperienceItem.title` of the overridden item (1-120 chars) |
| `item_organization` | `ExperienceItem.organization`, or null when the item has none (1-120 chars when present) |
| `slot_id` | The slot this item is assigned to; must be a slot of the selected pathway (`UNKNOWN_EVIDENCE_SLOT` on failure) |

## Version Pinning

Registry version bumps never silently re-map a live selection: coverage is always computed against the pinned `pathway_registry_version` until the user re-confirms on the current one (surfaced as a gentle prompt, never forced).
A selection pinned to a version the registry no longer serves surfaces `PATHWAY_REGISTRY_VERSION_MISMATCH` - surfaced, never silently re-mapped.

## Profile Update Policy

Selecting or changing a pathway creates a new profile version and invalidates the syllabus, tasks, and schedule, like a target-role change (see the policy table in `user-profile.schema.md`).
Evidence items are pathway-independent facts: changing pathway never resets evidence; only the slot mapping is recomputed against the new template.

## Invariants

- One item maps to at most one slot: `slot_overrides` entries are unique by the case-insensitive `(item_title, item_organization)` identity.
- `selected_at` is timezone-aware.
- Unknown fields are rejected (`extra="forbid"`).
- Registry membership of `pathway_id` and `slot_id` is a service-layer check against the pinned registry version, not a contract-shape check.

## Invalid Examples

```json
{ "pathway_id": "", "pathway_registry_version": "v1", "selected_at": "2026-07-19T12:00:00-07:00" }
```

Reason: empty `pathway_id`.

```json
{
  "pathway_id": "p",
  "pathway_registry_version": "v1",
  "selected_at": "2026-07-19T12:00:00",
  "slot_overrides": []
}
```

Reason: naive `selected_at` - timestamps must be timezone-aware.

```json
{
  "pathway_id": "p",
  "pathway_registry_version": "v1",
  "selected_at": "2026-07-19T12:00:00-07:00",
  "slot_overrides": [
    { "item_title": "Thing", "item_organization": "Org", "slot_id": "a" },
    { "item_title": "thing", "item_organization": "org", "slot_id": "b" }
  ]
}
```

Reason: duplicate item identity (case-insensitive) - one item may fill only one slot.

## Related Docs

- `../axioms/00-product-thesis.md`
- `../axioms/03-data-contracts.md`
- `pathway-template.schema.md`
- `user-profile.schema.md`
- `strategy-constraints.schema.md`
- `../implementation-plans/narrative-pathways/02-contracts-and-registry.md`
