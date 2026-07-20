# 00: Product Thesis

## Thesis

**LLMs propose. Deterministic infrastructure disposes.**

The product is a deterministic career-preparation and application-preparation orchestration system that converts a user's goal, timeline, availability, skill profile, motivation profile, and accountability preferences into a validated, dependency-aware, calendar-scheduled execution plan. It is not a generic autonomous agent, a content site, or a chatbot.

The system serves users preparing for interviews, college or graduate applications, career transitions, technical upskilling, certifications, or other high-stakes preparation goals where the gap between intention and execution is large.

LLMs are used only at bounded generation points: curriculum generation, task decomposition, reflection summaries, sponsor-safe progress explanations, user-facing explanations, and natural-language clarification. All control boundaries are deterministic: routing, validation, dependency checks, scheduling feasibility, approval gates, drift classification, accountability intervention triggers, sponsor report permissions, source confidence scoring, calendar writes, retry limits, cost limits, and concurrency locks.

Pathway fit, narrative gap computation, and story progress are computed deterministically from confirmed evidence; LLMs do not assign fit.

## Target User

The target user is a preparation candidate with a concrete goal and timeline. The strongest initial segment is new-grad or early-career software engineers preparing for backend, full-stack, or general software engineering interviews. Adjacent high-stakes segments — college or graduate admissions applicants, career transitioners, certification candidates — follow the same planning-and-accountability pattern and can be onboarded without architectural changes.

This user segment is attractive because:

- Goals are concrete.
- Timelines are often explicit.
- Study topics are semi-structured.
- Users already use calendars and task systems.
- Completion behavior can be measured.
- The pain of poor planning is high.

## Product Positioning

The product is positioned as:

> A reliable execution engine that turns high-stakes goals into validated plans, schedules them around your real calendar, and keeps you accountable based on how you actually execute.

This framing emphasizes:

- Reliability.
- User control.
- Calendar safety.
- Measurable progress.
- Adaptation.
- Privacy-first personalization.
- Accountability without surveillance.
- Privacy-first sponsor visibility.

The product is not framed as a fully autonomous agent.

## Moat

The moat is execution quality, not a static content corpus. Interview questions, admissions advice, essay guidance, study guides, company blogs, and learning materials are increasingly commoditized. Defensibility comes from:

- deterministic orchestration and validation;
- the ability to turn vague goals into structured, dependency-aware plans;
- safe calendar integration with preview, approval, verification, and rollback;
- adaptation based on actual completion telemetry;
- drift detection that explains why a plan stopped fitting reality;
- structured source claims that keep recommendations auditable;
- permissioned accountability pressure that helps users follow through without violating trust.

## MVP Direction

The MVP loop is:

- Structured onboarding.
- Motivation and accountability profiling.
- Structured syllabus generation.
- Task planning with schema validation.
- Deterministic validation layer.
- Draft schedule preview.
- Explicit calendar write after approval.
- Completion telemetry.
- Weekly check-in.
- Simple duration and workload calibration.
- Deterministic accountability interventions.

The MVP must prove five things:

1. The system can generate a useful structured syllabus.
2. The system can convert that syllabus into valid task plans.
3. The system can schedule tasks safely without calendar mistakes.
4. Users are willing to approve and follow the generated schedule.
5. Accountability interventions increase completion without damaging user trust.

The accountability system should be simple and deterministic in the MVP. It should not attempt to deeply infer personality, diagnose motivation, or act like a therapist. It should use observable behavior such as missed tasks, reschedules, check-in completion, and behind-schedule percentage.

## What the MVP Excludes

- Offline mode.
- Fully autonomous replanning.
- Per-user XGBoost or neural models.
- Silent calendar writes.
- Silent parent or sponsor reporting.
- Cross-user training without opt-in.
- Complex multi-calendar conflict resolution beyond core free/busy.
- General-purpose autonomous agent behavior.
- Unbounded planner-scheduler loops.
- AI therapy or mental-health coaching.
- Financial penalties, deposits, or commitment contracts involving real-money forfeiture.
- Parent surveillance dashboards.
- Raw calendar title or private note storage.
- Task-level sponsor visibility by default.

The product may create pressure, but that pressure must be explicit, user-approved, reversible, and permissioned.

The first version must be boring, predictable, and trustworthy.

## Why Determinism Matters

Reliable agentic systems need deterministic boundaries. Determinism gives the product:

1. **Inspectability** — engineers can understand why the system acted.
2. **Repeatability** — the same state produces the same route or validation result.
3. **Safety** — side effects are gated and reversible.
4. **Testability** — golden test cases can verify behavior.
5. **User trust** — users can preview and approve changes before execution.

## System Design Principle

> The LLM may propose a candidate. Code must decide whether that candidate is valid, feasible, safe, and approved.

## Why Calendar Safety Matters

Calendar writes affect the user's real life. A bad write can create missed commitments, duplicate events, or loss of trust. The Scheduler only drafts. The Calendar Write Manager is the only writer and requires explicit approval. See `06-calendar-safety.md`.

## Product Promise

The most important product promise is **reliability with trust-preserving pressure**. A user should be able to trust that the system will:

- never write to their calendar without approval;
- never silently mutate their active plan;
- never create duplicate events after a crash;
- never expose private progress data to parents or sponsors without explicit permission;
- always clearly explain why a plan, intervention, or report was generated.

## Final Directional Summary

This product should not be built as a generic autonomous agent. It should be built as a deterministic planning, scheduling, and accountability engine with LLM-powered structured generation.

The product earns trust by being predictable, inspectable, reversible, explicit, and permissioned. It must never silently write to the user's calendar, never let invalid LLM output reach the Scheduler, never mutate active plans without approval, never send parent or sponsor reports without permission, and never hide why something failed.

The strongest one-sentence architecture is:

> A deterministic planning, scheduling, and accountability engine where LLMs generate structured candidates, code validates and schedules them, users approve every calendar side effect, telemetry calibrates future workload, and permissioned accountability features help users follow through without exposing unnecessary private data.

If the five MVP proofs above hold, adaptive replanning, sponsor reporting, RAG quality, and personalization become valuable. If they do not hold, more agentic complexity will only make the system harder to trust.

The key product principle is:

> **Motivation is not an LLM tone problem. Motivation is product state.** The system represents motivation through structured preferences, completion telemetry, accountability contracts, deterministic intervention policies, and permissioned sponsor visibility — never through LLM-inferred personality or psychological labels.

## Related Docs

- `01-system-boundaries.md`
- `02-state-machine.md`
- `06-calendar-safety.md`
- `10-mvp-roadmap.md`
- `21-accountability-layer.md`
- `../specs/motivation-profile.schema.md`
- `../decisions/ADR-0001-deterministic-control-plane.md`
