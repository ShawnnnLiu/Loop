# 01: System Boundaries

## Principle

LLMs generate candidates. Deterministic services decide validity, routing, scheduling, approvals, writes, telemetry classification, accountability triggers, sponsor permissions, and retries.

LLMs are powerful but unreliable content generators. They may produce useful structured candidates, but they must not control the system's state, side effects, safety boundaries, accountability triggers, or sponsor permissions.

If the same state is passed into the same deterministic component, the same output must result.

The rule is simple: the LLM may write the message that says, "You are behind and here is the recovery plan." The deterministic policy engine must decide whether the user is behind, whether a recovery plan is needed, whether a sponsor report is allowed, and what data may be included.

## Allowed LLM Nodes

Only four nodes may call an LLM in the MVP:

- `StrategistNode` — proposes structured syllabus modules.
- `PlannerNode` — proposes task plans from validated syllabus units.
- `ReflectionSummaryNode` — summarizes user progress and friction.
- `UserFacingExplanationNode` — explains deterministic decisions in plain language.

LLMs may also be used for natural-language clarification during onboarding, but the resulting structured `user_profile` object must be deterministic.

LLM node output must be schema-validated before any consumer uses it.

## LLM Allowed Responsibilities

- Curriculum generation.
- Task decomposition.
- Reflection summaries.
- User-facing explanations.
- Natural-language clarification.
- Friendly accountability message wording.
- Sponsor-safe weekly summary wording.
- Recovery-plan explanations.

## LLM Forbidden Responsibilities

LLMs must not be used for:

- Routing or Supervisor transitions.
- Dependency validation.
- Calendar write decisions.
- Approval gate enforcement.
- Retry limit enforcement.
- Prerequisite computation.
- Source confidence scoring.
- Drift classification in the MVP.
- Accountability intervention classification.
- Sponsor report permission decisions.
- Parent notification decisions.
- Cost cap enforcement.
- Concurrency lock enforcement.

## Deterministic Ownership

Deterministic code must own:

- State transitions and Supervisor routing.
- Schema validation and graph validation.
- Scheduling feasibility.
- Approval gates.
- Calendar write permission, idempotency, verification, and rollback.
- Telemetry storage.
- Drift classification (MVP).
- Accountability classification.
- Sponsor permission checks.
- Progress report eligibility.
- Source confidence scoring.
- Cost and retry limits.
- Concurrency locks.
- Prerequisite status.

## Motivation Is Product State

Motivation must be treated as product state, not as LLM tone. The system represents motivation through:

- structured onboarding fields;
- observable completion telemetry;
- explicit accountability preferences;
- check-in history;
- deterministic intervention policies.

The LLM may make the experience feel warm, but code must decide when the user is behind, what intervention is allowed, and whether any external party may be notified. See `21-accountability-layer.md` and `../specs/motivation-profile.schema.md`.

## High-Level Flow

```text
User Profile
  → Motivation Profile
  → Accountability Contract
  → Structured Syllabus
  → Task Plan
  → Validation
  → Draft Schedule
  → User Approval
  → Calendar Write
  → Telemetry
  → Accountability Policy Engine
  → Drift Classification
  → Replanning or Recovery
```

This is a cyclical orchestration system. The user may complete tasks, miss tasks, reschedule tasks, change goals, complete weekly check-ins, or opt into sponsor reporting. Those events feed telemetry and may trigger drift classification, accountability interventions, recovery planning, or replanning.

The task graph itself must remain acyclic (see `15-plan-versioning-and-diffs.md`). The accountability graph must not mutate the task graph directly. It may recommend actions such as user nudges, weekly check-ins, sponsor summaries, recovery plan drafts, scope reductions, or schedule revisions. Any plan or schedule mutation still requires validation and user approval.

## Component Map

| Component | Role | LLM-Based? | Deterministic? |
| --- | --- | --- | --- |
| Supervisor | Routes state to next node | No | Yes |
| Structured Onboarding | Captures goal, constraints, and user profile | No | Yes |
| Motivation Profiler | Captures accountability preferences and procrastination risk | No | Yes |
| Accountability Contract Manager | Stores commitment rules, check-in settings, and sponsor permissions | No | Yes |
| Curriculum Strategist | Generates syllabus modules | Yes | Schema-bound |
| RAG / Source Claim Store | Retrieves and scores evidence | Retrieval may use embeddings | Scoring is deterministic |
| Execution Planner | Generates tasks | Yes | Schema-bound |
| Validation Layer | Validates tasks and plan | No | Yes |
| Deterministic Scheduler | Creates draft schedule | No | Yes |
| Approval Gate Manager | Requires user approval | No | Yes |
| Calendar Write Manager | Writes approved events | No | Yes |
| Telemetry Logger | Records completion, duration, reschedule, and check-in data | No | Yes |
| Accountability Policy Engine | Determines nudges, check-ins, sponsor reports, and recovery triggers | No | Yes |
| Sponsor Report Generator | Creates permissioned progress summaries | Wording may use LLM | Permissions are deterministic |
| Drift Classifier | Classifies execution drift | No (MVP) | Yes |
| Duration Calibration Engine | Updates duration multipliers | No (MVP) | Yes |
| Checkpointing Layer | Persists state | No | Yes |
| Metrics Layer | Tracks system quality | No | Yes |

## Architecture Stages

| Stage | Input | Owner | Output | Deterministic? | Failure Mode | Recovery |
| --- | --- | --- | --- | --- | --- | --- |
| Onboarding | User answers | Onboarding service | `user_profile` | Yes | Missing required fields | Ask user for missing fields |
| Syllabus generation | `user_profile`, source claims | `StrategistNode` | `syllabus_units` | No, schema-bound | Invalid module schema | Repair or regenerate |
| Source scoring | Retrieved claims | Source system | Scored claims | Yes | Source missing metadata | Mark low confidence |
| Task planning | profile + syllabus | `PlannerNode` | `task_plan` | No, schema-bound | Invalid task graph | Validator repair loop |
| Validation | `task_plan` | Validator | `validation_result` | Yes | Schema/graph/user-fit failure | Repair or approval gate |
| Scheduling | validated tasks + free/busy | Scheduler | draft schedule | Yes | Insufficient capacity | Debug payload + repair options |
| Approval | draft schedule | Approval Gate | `approval_event` | Yes | User rejects | Revise draft or stop |
| Calendar write | approval + draft | Calendar Write Manager | calendar events | Yes | Partial write | `run_id`/`task_id` recovery |
| Telemetry | completion events | Telemetry Logger | telemetry log | Yes | Invalid event | Reject event |
| Drift classification | telemetry | Drift Classifier | `drift_event` | Yes | Insufficient evidence | No action |
| Replanning | `drift_event` + profile | Strategist/Planner | draft revision | Mixed | Invalid revision | Validation and approval gate |

## Boundary Tests

Every implementation that calls an LLM must have tests proving that invalid output is rejected before reaching deterministic consumers. Every side-effecting implementation must have tests proving that no prompt can bypass approval and write directly.

## Related Docs

- `02-state-machine.md`
- `03-data-contracts.md`
- `04-validation-layer.md`
- `08-rag-source-claims.md`
- `16-reliability-patterns.md`
- `../decisions/ADR-0001-deterministic-control-plane.md`
