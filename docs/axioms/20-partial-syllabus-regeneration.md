# 20: Partial Syllabus Regeneration

## MVP Stance

Partial syllabus updates are **not part of the MVP**. The MVP path for any profile change is full syllabus regeneration, gated behind validation and approval (see `12-edge-case-policy-engine.md`).

This axiom defines the Phase 2/3 design so that current code does not preclude it.

## Interim Step Shipped (2026-07-05, UX pass D4)

An interim, context-only step now precedes this axiom's Phase 2/3 design:

- **Stage 1 — prior-plan anchoring.** The recovery-replan Planner call embeds the active plan's surviving tasks (completed/dropped filtered out deterministically) plus the recovery mode, with a preserve-ids/titles/durations-unless-affected instruction. This is prompt context only: the model is anchored, not constrained. Deterministic validation is unchanged, and nothing enforces preservation — a replan that ignores the anchor still validates on its own merits.
- **Stage 2 — deterministic diff surfacing.** The old→new plan-content diff (`planning/diff.py`, producing the `plan-diff.schema.md` contract) is computed by code and surfaced at review/approval, so the user evaluates the delta instead of a wall of blocks.

Validator-enforced preservation (`PATCH_SCOPE_VIOLATION`, the patch classifier, delta-regeneration prompts) remains Phase 2/3 work as specified below; the interim step neither implements nor precludes it.

## Why a Phase 2/3 Feature

A small profile change (one new weakness, a 10% timeline adjustment, a new deep-work window) should not invalidate an entire syllabus. Full regeneration is wasteful, costly, and disruptive to users mid-plan. Partial regeneration preserves user investment in the existing plan while still respecting validation and approval invariants.

The decision of whether a change is "small enough" for partial regeneration is **deterministic**. The generation itself is LLM-driven within tight scope.

## Deterministic Patch-vs-Regenerate Classifier

A profile delta is classified into one of three categories by pure code:

| Change Type | Classification | Action |
| --- | --- | --- |
| Added or removed weakness in single module | `partial_patch_eligible` | Generate patch for affected module only |
| Added or removed strength in single module | `partial_patch_eligible` | Adjust task volume in module |
| Changed weekly hours by < 25% | `partial_patch_eligible` | Adjust task volume across plan |
| Changed weekly hours by >= 25% | `full_regenerate_required` | Full regeneration |
| Changed timeline by < 25% | `partial_patch_eligible` | Compress or expand schedule |
| Changed timeline by >= 25% | `full_regenerate_required` | Full regeneration |
| Changed target role | `full_regenerate_required` | Full regeneration |
| Added or removed target company | `partial_patch_eligible` if the new company shares >= 70% pattern overlap with existing targets, else `full_regenerate_required` | Patch or full |
| Changed experience level | `full_regenerate_required` | Full regeneration |
| Changed deep work windows | `schedule_only_repatch` | Reschedule existing tasks; no syllabus change |
| Changed hard constraints | `schedule_only_repatch` | Reschedule existing tasks; no syllabus change |

The classifier outputs:

- `classification` — one of `partial_patch_eligible`, `full_regenerate_required`, `schedule_only_repatch`.
- `patch_scope` — the set of `module_id` values eligible for patching when applicable.
- `patch_reason` — a typed `reason_code` describing what triggered the patch.

The classifier must never call an LLM. It is deterministic policy, with thresholds that live in the same configuration block as the policy engine in `12-edge-case-policy-engine.md`.

## Partial Patch Flow

When the classifier returns `partial_patch_eligible`:

1. **Identify affected scope.** Code computes which modules, which tasks, and what the change is. The result is a structured `patch_scope` payload.
2. **LLM generates the patch within scope.** The Strategist receives a constrained prompt: "Modify only modules X and Y to reflect [specific change]. Do not modify other modules. Output a delta, not a full syllabus."
3. **Validation applies the same rules as full generation, plus a scope check.** The patch must not modify modules outside the declared scope. Out-of-scope modifications are validation failures with reason code `PATCH_SCOPE_VIOLATION`.
4. **Diff preview.** A deterministic diff (see `15-plan-versioning-and-diffs.md` and `../specs/plan-diff.schema.md`) shows the user exactly what changed at all three levels.
5. **Approval gate.** No task or schedule changes are committed before the user approves.
6. **Downstream effects.** Task regeneration and rescheduling are computed deterministically from the patched syllabus.

## Patch Failure Fallback

If a patch fails validation **twice** (the same hard cap as full generation), the system falls back to **full regeneration** with explicit user notification: "A small update couldn't be applied cleanly. Generating a full revision instead."

The fallback emits the typed `reason_code` `PATCH_FALLBACK_TO_FULL` and is logged for engineering review.

## Schedule-Only Repatch Flow

When the classifier returns `schedule_only_repatch` (for example, the user changed deep-work windows):

1. The syllabus is **not** modified.
2. The task plan is **not** modified.
3. The Scheduler reruns against the existing validated tasks with the new constraints.
4. The deterministic diff is computed against the prior schedule (not against the prior plan version).
5. Approval is still required before any calendar mutation.

## Audit

Every patch records:

- `patch_scope`
- `patch_reason`
- `classification`
- `original_syllabus_version`
- `patched_syllabus_version`
- LLM input and output for engineering review
- Validation result and any repair attempts

The audit log is append-only and immutable.

## Invariants

- The patch-vs-regenerate decision is deterministic.
- The Strategist must not modify modules outside `patch_scope`.
- A patch must pass the same validation rules as a full syllabus generation.
- A patch must produce a deterministic diff before any user-visible change.
- A patch must not bypass approval before downstream task or schedule changes are committed.
- Schedule-only repatches do not require new syllabus or task validation; they require Scheduler validation only.

## Why This Sequencing

Implementing partial regeneration before full regeneration is reliable would multiply the surface area for bugs. The MVP must prove that full generation, validation, scheduling, and approval work end-to-end. Phase 2/3 then adds the optimization of patching, with the deterministic classifier acting as a gate so the optimization can never compromise the invariants established in Phase 1.

## Related Docs

- `04-validation-layer.md`
- `08-rag-source-claims.md`
- `12-edge-case-policy-engine.md`
- `15-plan-versioning-and-diffs.md`
- `16-reliability-patterns.md`
- `../specs/syllabus-units.schema.md`
- `../specs/plan-diff.schema.md`
