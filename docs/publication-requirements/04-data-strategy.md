# 04 · Long-Term Data Strategy — Useful Without PII

Written 2026-07-16. Records the decision on what Loop collects for the long
term, why that data is the durable asset, and the rules that keep it free of
PII. Informs the privacy policy ([03 §2](03-service-readiness.md)) and the
compliance posture stated in verification ([01 §6](01-google-oauth-verification.md)).

## 1. Thesis: the goldmine is about tasks and skills, not people

The long-term asset is **per-node learning curves over the curated pathway
registry**: how long real learners take to master skill X in track Y, where
they stall, what gets dropped vs. rescheduled, how mastery decays. Value and
privacy barely overlap here — the data is about tasks and skills, so PII
avoidance costs almost nothing.

Why this data compounds:

- `CLAUDE.md` axiom: validation thresholds, drift thresholds, and priors are
  "heuristic priors until calibrated." **This dataset is the calibration
  corpus** the axioms are already waiting for.
- Per-node difficulty curves for Loop's own pathway trees exist nowhere
  else; every active user deepens them.
- Aggregate curves, unlike résumés or calendar data, survive user deletion
  legitimately (see §3.3).

**Mastery outcomes are the highest-value label** in the stream: they turn
duration telemetry into difficulty calibration (supervision signal for
time-to-mastery, drop-point, and decay estimates).

## 2. The template already exists in the codebase — generalize it

Three shipped pieces are the pattern; new collection copies them, it does
not invent a new posture:

| Existing piece | The property to copy |
| --- | --- |
| `TelemetryEvent` (`contracts/telemetry.py`) | **No `user_id` on the event.** Fields are task_id, scheduled/actual duration, completed, reschedule count, subjective difficulty 1–5, `data_quality`. |
| `PooledDurationModel` (`contracts/pooled_duration_model.py`, ADR-0007) | "Contains no user identifiers — only feature buckets and aggregate statistics." Coarse buckets (`TimeOfDayBand`, `DayOfWeek`, `TaskCategory`, `ExperienceLevel`), shrinkage toward a global prior, deterministic rebuild. |
| Axiom-07 consent (`contracts/consent_record.py`) | One record per explicit data-use scope (`pooled_training`, `cohort_retrieval`); revoke is terminal; re-consent is a new record. Honest, auditable opt-in. |

## 3. The rules

### 3.1 Closed vocabularies only in the research stream

The long-term stream may contain: pathway-node IDs, skill-taxonomy IDs,
career-track IDs, reason codes, enums, numbers, coarse time buckets.
**Never free text.** Free text is the only channel through which PII can
leak into structural data. The precedent is already set: résumé extraction
is categories-not-names (RI decision log). Goal prose, check-in notes, and
raw résumé text live in the identity store and never cross over.

### 3.2 Identity/research split — and what it does NOT buy

- Identity store: email, OAuth tokens, raw résumé, timezone, sessions.
- Research store: events keyed by an opaque random ID; the join key lives
  only on the identity side.
- **Pseudonymized is not anonymized.** While the join key exists, the event
  stream is still personal data under GDPR/CCPA and the privacy policy must
  treat it as such. True anonymization happens at aggregation (§3.3). Do
  not write "anonymous" in the policy for anything row-level.

### 3.3 Aggregate-then-expire makes it a permanent asset

- Raw events are kept for a bounded window (pick and document one — e.g.
  18 months; heuristic, the commitment matters more than the number).
- Scheduled training/aggregation produces **versioned artifacts** (pooled
  models, per-node difficulty/mastery stats). The artifacts are the
  goldmine; they contain no identifiers.
- Deletion story this buys, verbatim for the privacy policy: *"Deleting
  your account deletes your identity data and your event history. Aggregate
  statistics that cannot identify you are retained; your events are
  excluded from the next scheduled retraining."*

### 3.4 Coarsen quasi-identifiers; suppress small cells

- No absolute timestamps in long-term storage — time-of-day band +
  day-of-week (already the pooled-model convention).
- Timezone: drop, or bucket to coarse region, before the research store.
- Re-identification risk lives in rare combinations
  (`career_track × experience_level × uncommon skill set`). Shrinkage is a
  statistics tool, not a privacy tool — the privacy tool is **minimum cell
  size**: never emit, export, or publish a bucket with fewer than k
  contributors (k=5 conventional floor; heuristic, document the choice).

### 3.5 Google-derived data never enters the goldmine

Busy/free ranges — and features *derived* from them — are Google user data
under the [Limited Use policy](https://developers.google.com/terms/api-services-user-data-policy).
They are transient scheduling input only. The clean line:

- **App facts (allowed):** which slot the scheduler chose, session
  completed/dropped/rescheduled, drift classification, mastery outcome.
- **Google facts (excluded):** busy ranges, fragmentation features computed
  from busy ranges, anything else read via `calendar.freebusy`.

This also keeps the verification claims in [01 §6](01-google-oauth-verification.md)
simple and true.

## 4. The one new engineering artifact: mastery/progression events

New contract following the `TelemetryEvent` posture (spec-first per the
schema rules — `docs/specs/` before Pydantic before fixtures):

- Sketch fields: `pathway_node_id` (registry ID), `attempt_count`,
  `time_to_mastery_min`, `mastery_outcome` (enum), `subjective_difficulty`,
  `data_quality`, coarse time bucket. No user_id on the event, no free
  text.
- **Keep `data_quality` provenance tagging** — mastery self-reports are
  noisy labels; the long-term dataset must record label provenance or the
  calibration inherits silent bias.
- **Consent:** if mastery-data use doesn't fit the existing
  `pooled_training` / `cohort_retrieval` scope definitions, add a third
  axiom-07 scope rather than stretching one. One scope = one data use.

## 5. What this lets the privacy policy say

Because of §§1–4, the policy can be specific instead of boilerplate — which
is both more honest and a better look in Google's review:

> We collect de-identified skill-progression data — which pathway skills
> you work on, how long sessions take, completion and mastery outcomes — to
> calibrate difficulty and duration estimates for everyone. This is opt-in,
> revocable at any time, and never includes your calendar contents, résumé
> text, or anything you write in free text.

Collection summary:

| Category | Examples | Posture |
| --- | --- | --- |
| Aggregate artifacts | pooled models, per-node difficulty curves | Keep indefinitely; the asset |
| Research events (pseudonymous) | telemetry, mastery events, dispositions | Consent-gated, bounded retention, aggregate-then-expire |
| Identity data | email, tokens, raw résumé, timezone | Service delivery only; deleted on account deletion |
| Google calendar data | busy/free ranges | Transient input; never stored long-term, never in research data |
| Free text | goals, notes, résumé prose | Never in the research stream |
