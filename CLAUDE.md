# Claude Operating Contract

This file is mandatory project context for Claude Code. Follow it strictly.

The repository authority order is:

1. User instructions in the current chat.
2. `CLAUDE.md`.
3. `AGENTS.md`.
4. `.cursor/rules/`.
5. `docs/axioms/`, `docs/specs/`, `docs/decisions/`, and implementation plans.
6. Existing code and tests.

If any instruction conflicts with the project axioms, stop and ask the user.

## Project Mission

Agentic Calendar is a deterministic career-preparation orchestration engine.

It turns user goals, availability, validated learning structure, and progress signals into safe, auditable study plans and calendar drafts.

It is not:

- a generic chatbot;
- an autonomous calendar assistant;
- a content-generation product;
- a system where LLM prose controls workflow state.

Core thesis:

> LLMs propose. Deterministic infrastructure disposes.

LLMs may generate structured candidates and user-facing explanations. Deterministic code owns routing, validation, scheduling, approval gates, calendar writes, telemetry, drift classification, retry limits, concurrency locks, source confidence scoring, and side-effect safety.

## Mandatory First Step

Before any substantive change, read:

- `AGENTS.md`;
- the relevant file in `docs/axioms/`;
- the relevant schema contract in `docs/specs/` if object shape, validation, serialization, fixtures, or generated schemas may change;
- the relevant implementation plan in `docs/implementation-plans/` if the change touches roadmap scope.

Do not edit first and read later.

## Permission Boundaries

Allowed without additional user confirmation:

- Read project files.
- Edit project source, tests, docs, and fixtures when directly required by the user's request.
- Run local deterministic checks from `backend/`.
- Add focused tests for changed behavior.
- Regenerate schemas only when schema contracts or Pydantic contract models intentionally change.

Ask the user before:

- Installing new dependencies.
- Changing dependency versions.
- Running networked commands.
- Creating commits.
- Pushing branches or tags.
- Opening pull requests.
- Deleting files.
- Moving large groups of files.
- Changing public contracts, schemas, or architecture beyond the stated task.
- Changing project rules, `AGENTS.md`, `.cursor/rules/`, or this file.
- Running commands that write outside the repository.
- Running commands that contact calendar providers, LLM providers, or other external services.

Never do these unless the user explicitly requests the exact action:

- `git reset --hard`
- `git clean`
- `git checkout -- <path>`
- force push
- deleting untracked work
- rewriting history
- modifying secrets, credentials, tokens, or `.env` files
- executing production calendar writes
- bypassing tests, hooks, or validation to make a change appear complete

## Non-Negotiable Axioms

- No silent calendar writes.
- No LLM-controlled routing.
- No invalid Planner output may reach the Scheduler.
- No calendar write may occur without `approval_event_id`.
- Prerequisites are computed deterministically from dependencies and completion state.
- The active plan is never mutated directly; use plan versions.
- Every failure must produce a typed `reason_code`.
- Every external side effect must support dry-run, verification, and rollback.
- Drift classification is deterministic in the MVP.
- Source confidence is scored deterministically; LLMs do not assign confidence.
- The MVP is always-online for plan mutations and calendar writes.
- Offline task completion is the only allowed offline mutation and must be tagged with `data_quality`.
- Every calendar write must pass an `approved_payload_hash` recheck against the live draft, recomputed under the recorded `hash_canonicalization_version`.
- Validation thresholds, drift thresholds, and source confidence base scores are heuristic priors until calibrated.

## Calendar Safety

The Scheduler creates draft schedules only.

Calendar Write Manager is the only calendar writer.

No calendar write is valid unless all of these are present:

- `approval_event_id`;
- `run_id`;
- `task_id`;
- `plan_version`;
- `approved_payload_hash`;
- calendar target identifier.

Every calendar write path must support:

- dry-run;
- duplicate detection by metadata;
- verification read after write;
- rollback by stored `calendar_event_mapping`.

Do not store raw calendar event titles or descriptions.

## Architecture Boundaries

Allowed LLM node classes:

- `StrategistNode`
- `PlannerNode`
- `ReflectionSummaryNode`
- `UserFacingExplanationNode`

Only `llm_nodes/` and `tools/` may import LLM SDKs.

Deterministic code owns:

- Supervisor routing;
- state transitions;
- validation and repair retry limits;
- prerequisite status;
- scheduling;
- approval gates;
- calendar writes and rollback;
- telemetry storage;
- MVP drift classification;
- source confidence scoring.

Do not allow prompts, chat history, prose explanations, or calendar text to become control-plane state.

Backend package boundaries:

- `common/`: tiny shared kernel.
- `contracts/`: Pydantic models, one module per spec.
- `supervisor/`: pure routing and transitions.
- `prerequisites/`: deterministic prerequisite computation.
- `validation/`: schema, graph, coverage, user-fit, and scheduling validation.
- `scheduler/`: pure greedy MVP scheduler.
- `planning/`: immutable plan versions and generation history.
- `llm_nodes/`: only allowed LLM integration area.
- `tools/`: operator CLIs.

Region packages must not import sibling regions. Cross-region communication goes through `contracts/` and `common/`. Import boundaries are enforced by `.importlinter`.

## Schema And Contract Rules

Treat `docs/specs/` as contracts between LLM nodes and deterministic services.

Before changing object shape or semantics:

1. Read the relevant `docs/specs/*.schema.md`.
2. Update the spec first.
3. Update the Pydantic contract model.
4. Update valid and invalid fixtures.
5. Update generated JSON schemas if applicable.
6. Update tests.

Rules:

- Reject invalid LLM output before consumers use it.
- Keep `task_plan.prerequisites_met` forbidden.
- Compute prerequisite status deterministically.
- Preserve `run_id`, `plan_version`, `task_id`, and typed `reason_code` where required.
- Include invalid fixtures for schema and invariant tests.

## Validation And Repair Rules

Validation checks must be deterministic.

Required validation categories:

- schema;
- graph;
- coverage;
- user-fit;
- scheduling preconditions.

Repair is bounded:

- Do not silently drop validation failures.
- Do not exceed two repair attempts per artifact.
- Do not exceed two Scheduler-Planner iterations.
- Every failure must retain typed `reason_code` information.

Prompt wording is not a test oracle. Use fixtures, contracts, and deterministic assertions.

## Scheduler Rules

The Scheduler is deterministic.

It must:

- consume only validated inputs;
- produce draft-only calendar output;
- preserve typed `reason_code` values;
- include debug payloads for failures;
- never write to a calendar;
- never infer prerequisites from LLM prose.

Capacity failures and fragmentation failures must remain distinguishable. Preserve existing behavior unless the user explicitly asks to change scheduler policy and the relevant axiom/spec is updated.

## Testing Requirements

Add or update tests for changes touching:

- typed `reason_code` values;
- valid and invalid state transitions;
- schema validation;
- graph validation;
- coverage validation;
- user-fit validation;
- scheduling validation;
- Scheduler failure debug payloads;
- calendar preview, approval, write, verification, duplicate prevention, and rollback;
- telemetry-derived drift classification;
- fixtures or contract behavior.

Invalid fixtures must include expected structured violations where the existing test pattern requires them.

Use deterministic assertions. Do not rely on prompt text as proof of behavior.

## Local Commands

Run commands from `backend/` unless otherwise stated.

Setup:

```bash
uv sync --extra dev
```

Focused checks:

```bash
make test-fast
make lint
make typecheck
make boundaries
```

Full check:

```bash
make check
```

Schema generation, only after intentional contract changes:

```bash
make schemas
```

Formatting, only when appropriate for changed files:

```bash
make format
```

Do not use formatting to hide unrelated edits.

## Git Rules

Assume the working tree may contain user changes.

- Check status before commits.
- Do not revert changes you did not make.
- Do not delete untracked files unless the user explicitly asks.
- Do not create commits unless the user explicitly asks.
- Do not push unless the user explicitly asks.
- Do not amend commits unless the user explicitly asks and it is safe.
- Do not rewrite history unless the user explicitly asks and confirms the risk.

## Working Style

Prefer small, directly scoped changes.

Before editing:

- identify the relevant contract, axiom, or existing pattern;
- inspect nearby tests;
- understand current behavior.

During implementation:

- preserve architecture boundaries;
- avoid new abstractions unless they remove real complexity or match an established local pattern;
- keep structured data structured;
- keep control-plane state explicit;
- avoid compatibility shims for unshipped branch-local work unless the user requests them.

After implementation:

- run the narrowest meaningful checks first;
- run broader checks when touching shared behavior;
- report commands run and failures honestly;
- state any remaining risk.

## Stop Conditions

Stop and ask the user if:

- a requested change conflicts with a non-negotiable axiom;
- the change requires calendar, LLM-provider, or other external-service access;
- the implementation would require breaking import boundaries;
- the schema/spec implications are unclear;
- secrets or credentials are needed;
- existing uncommitted changes block a safe edit;
- tests reveal failures outside the scope of the task and the fix is not obvious.
