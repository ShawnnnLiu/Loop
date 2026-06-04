# ADR-0006: Why the LLM Never Touches the Calendar

## Status

Accepted

## Context

The system uses LLMs to propose syllabus units, task plans, reflection summaries, and user-facing explanations. These are probabilistic content generators: useful, fluent, and occasionally wrong in ways that are hard to detect from the text alone. A calendar write, by contrast, is an irreversible-feeling side effect on a real person's commitments — a duplicate event or a silently dropped task erodes trust immediately.

The repeated question from anyone reading the architecture is: *where exactly is the line between what the model does and what deterministic code does, and why is it drawn there?* The reasoning is spread across `00-product-thesis.md`, `01-system-boundaries.md`, ADR-0001, and ADR-0002. This ADR consolidates it into one decision and makes the most subtle part explicit.

## Decision

The LLM proposes structured candidates and writes user-facing prose. Deterministic infrastructure disposes: routing, validation, scheduling, approval gates, calendar writes, verification, rollback, telemetry storage, drift classification, source confidence, retry limits, and concurrency locks.

The line is drawn at **side effects and safety-bearing decisions**, not at "anything hard." Concretely:

- The model may generate a syllabus and a task plan. It may **not** decide they are valid, schedulable, or safe to write. Validation, scheduling, and the approval gate are deterministic.
- No calendar write is valid without `approval_event_id`, `run_id`, `task_id`, `plan_version`, `approved_payload_hash`, and a calendar target. The Calendar Write Manager is the only writer. A prompt cannot assemble these; only the deterministic flow can.
- The boundary case that makes the rule concrete: **drift classification is deterministic; the drift reflection is generated.** A rule-based classifier decides *that* the user is behind and *what kind* of drift it is (`low_engagement`, `topic_avoidance`, …) from observable telemetry. The `ReflectionSummaryNode` may then explain that result in supportive language. The model describes behavior; it never diagnoses identity, and it never decides whether the user is behind or whether anyone is notified.

The same split governs accountability and sponsor reporting: the policy engine decides whether a report is allowed and what it may contain; the LLM may only word the summary inside those permissions.

## Why Here and Not Elsewhere

- **Auditability and repeatability.** Same state into a deterministic component yields the same output. A schedule or a write can be reconstructed and replayed; a sampled token stream cannot.
- **Detectability of error.** A wrong task estimate fails a validation check with a typed `reason_code`. A wrong calendar write would just be wrong. Putting the model before the validators means its mistakes are caught; putting it after them would mean trusting it.
- **Reversibility.** Every disposed action has dry-run, verification, and rollback (`16-reliability-patterns.md`). Generation has none of these, so generation must never be the last step before a side effect.
- **Trust is the product.** The thesis is that users approve and follow the plan. One silent or duplicated write costs more trust than fluent prose buys.

The propose side is still held to a standard — it is graded, instrumented, and bounded by `22-llm-evaluation-and-observability.md`. Measuring proposal quality and observing every call reinforces this boundary rather than weakening it: the model gets better candidates and full telemetry, and still touches nothing downstream of the validators.

## Consequences

- More steps and less autonomy than an "agent that manages your calendar," by design.
- Every side effect is previewable, verifiable, and reversible.
- The four allowed nodes are the only LLM surface; new model use requires revisiting `01-system-boundaries.md`, not just adding a call site.
- Generation failures are first-class typed errors (`22`), not silent gaps — and none of them can reach a calendar write.

## Related Docs

- `../axioms/00-product-thesis.md`
- `../axioms/01-system-boundaries.md`
- `../axioms/06-calendar-safety.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/16-reliability-patterns.md`
- `../axioms/22-llm-evaluation-and-observability.md`
- `ADR-0001-deterministic-control-plane.md`
- `ADR-0002-preview-only-calendar-writes.md`
