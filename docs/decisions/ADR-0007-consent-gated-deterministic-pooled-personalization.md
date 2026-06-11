# ADR-0007: Consent-Gated Deterministic Pooled Personalization

## Status

Accepted

## Context

ADR-0004 deferred all cross-user and per-user model work out of the MVP: the
core loop had to be proven first with heuristic estimates, deterministic drift
triggers, and simple per-user category multipliers. That precondition is now
met for the purposes of Phase 6: Phases 1–5 and the Phase 7 accountability MVP
are merged, and the user accepted the Phase 7 production-proving test pass
(commit `97998b8`, 1731 deterministic tests green) as satisfying the "proven in
production" gate in the Phase 6 plan.

Phase 6 needs cross-user signal (axiom 17 Phase 3) and finer per-user
refinement (axiom 17 Phase 4) without giving up the properties that ADR-0004
protected: explainability, cheapness, debuggability, and privacy-first
defaults (axiom 07: no cross-user training data without opt-in).

## Decision

1. **The pooled "model" is deterministic, not ML.** The Phase 6 pooled
   duration estimator is a versioned artifact of feature-bucketed pooled
   multipliers with sample-size shrinkage toward a global prior — pure
   arithmetic over explicit features (axiom 17 Phase 3 feature list), trained
   by a pure function and replayable to an identical content hash from the
   same inputs. No gradient descent, no opaque weights, no inference service.
   ADR-0004's ban on per-user **ML** models stays in force; this ADR does not
   supersede it, it extends it with the allowed deterministic path.

2. **Every cross-user data use is consent-gated.** A user's telemetry enters
   pooled training, and cohort-level retrieval ranking, only under an explicit
   per-scope `consent_record` (`pooled_training`, `cohort_retrieval`).
   Consent is enforced at **training time and serving time**: revocation
   removes the user's events from the next artifact build and immediately
   stops consent-scoped serving lookups. Consent state is a deterministic
   grant/revoke state machine; re-consent is a new record, never a
   reactivation.

3. **Every consent-scoped access is audited.** Reads for pooled training,
   pooled serving, and cohort retrieval — and every view/export/delete data
   control — write an append-only `data_access_audit` entry with a typed
   purpose, accessor, outcome, and `reason_code` (`CONSENT_MISSING`,
   `CONSENT_REVOKED`, `DATA_EXPORTED`, `DATA_DELETED`). The audit log stores
   identifiers and outcomes only, never content.

4. **Users can view, export, and delete their data.** Operator CLIs expose
   the three data controls. Delete removes the user's rows from every store
   the composition root registers and writes a `DATA_DELETED` audit entry;
   the deletion audit trail itself is retained.

5. **Per-user refinement stays behind the power-user gate.** Finer per-user
   multipliers (Phase 6c) train only when the axiom 17 Phase 4 thresholds are
   met (200+ completed tasks, 30+ completions in the category, multi-week
   stability), evaluated deterministically with a per-criterion typed reason
   code so eligibility is auditable. Ineligible users keep the pooled →
   per-user-category → heuristic fallback chain unchanged.

6. **Pooled output feeds the Scheduler; it never replaces it.** Pooled
   failure, sparsity, or absence falls back deterministically (pooled bucket →
   Phase 2 per-user category multiplier → axiom 17 Phase 1 heuristics) with a
   typed reason code, and never blocks planning.

## Honesty Constraint

The MVP is single-user. There is no real multi-user telemetry, and this ADR
must not imply otherwise. Pooled training is exercised over **multi-user
fixture telemetry with synthetic user ids**. That proves the architecture —
consent gating at both train and serve time, shrinkage arithmetic, artifact
versioning/replay, and the fallback chain — without fabricating production
claims. All shrinkage floors, sample-size thresholds, and stability windows
introduced in Phase 6 are uncalibrated heuristic priors (axiom 07 threshold
honesty) until real multi-user data exists.

## Consequences

- Cross-user personalization arrives with the same auditability guarantees as
  calendar writes: explicit consent artifacts, typed reason codes, append-only
  audit logs, and deterministic replay.
- Consent checks add a gate (and an audit write) in front of pooled training
  and consent-scoped serving paths; deterministic fallbacks keep planning
  unblocked when the gate denies.
- A future real ML model would require a new ADR superseding ADR-0004; nothing
  in Phase 6 creates one.

## Related Docs

- `ADR-0004-no-per-user-ml-model-in-mvp.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/09-cost-and-metrics.md`
- `../axioms/17-duration-estimation.md`
- `../specs/consent-record.schema.md`
- `../specs/data-access-audit.schema.md`
- `../specs/telemetry.schema.md`
- `../implementation-plans/phase-6-advanced-personalization.md`
