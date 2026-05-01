# Phase 3: Sponsor and Parent Reporting

## Goal

Support optional accountability through permissioned sponsor visibility. Sponsor reports are opt-in, explicit, revocable, and privacy-filtered.

The goal is to prove that the system can expose useful progress information to a trusted third party without violating user trust or leaking private content.

## Required Docs

- `../../AGENTS.md`
- `../axioms/06-calendar-safety.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/16-reliability-patterns.md`
- `../axioms/21-accountability-layer.md`
- `../specs/motivation-profile.schema.md`
- `../specs/telemetry.schema.md`

## Deliverables

- Sponsor entity model (`sponsors` table).
- Sponsor invite flow with explicit user acceptance and revocation.
- Sponsor permission levels (`none`, `summary_only`, `milestone_progress`, `task_completion`).
- Sponsor report schema (see `21-accountability-layer.md`).
- Sponsor report approval gate (`requires_user_approval_before_send`).
- Weekly sponsor summary generation.
- Report delivery logs (`notification_logs`, `sponsor_reports`).
- Deterministic privacy filter that rejects disallowed content before any LLM wording pass.

## Acceptance Criteria

- No sponsor report is generated or sent without `sponsor_enabled: true` and a non-`none` `sponsor_visibility_level`.
- Sponsor reports pass through the deterministic privacy filter before any LLM wording; raw calendar titles, essay drafts, private notes, and psychological labels never reach the sponsor payload.
- Revoking sponsor permission takes effect before the next generated report and does not break the user's active plan.
- Sponsor report drafts record both trigger reason code (e.g., `SPONSOR_REPORT_PENDING`) and the user's approval event before send.
- Every sponsor report delivery is logged with `report_id`, `sponsor_id`, `visibility_level`, and status.
- `SPONSOR_PERMISSION_MISSING` and `SPONSOR_VISIBILITY_VIOLATION` are emitted on policy violations and block send.

## Explicit Non-Goals

- Live parent surveillance dashboards.
- Raw calendar sharing.
- Essay draft sharing by default.
- Sponsor control over the user's plan without user approval.
- Financial penalties or deposit-based commitment contracts.

## Test Expectations

- Golden tests for sponsor enable, disable, and visibility change (scenarios 17–20 in `../golden-test-cases.md`).
- Privacy filter tests that prove disallowed fields are rejected before LLM wording.
- Approval gate tests that prove reports are never sent without explicit user approval when required.
- Permission revocation tests that prove the active plan survives revocation.
- Audit log tests for every sponsor report generation and delivery event.
