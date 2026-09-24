# Implementation Plans — Index

Convention: every plan carries a `Status:` line near the top of its entry
doc (the folder's `README.md` or `00-overview.md`, or the file itself for
single-file plans). When a plan is fully implemented and merged to `main`,
it moves into `completed/`. The top level of this folder therefore lists
only active or not-yet-started work. The `Status:` line in each plan is the
authority; this table is a navigation aid.

## Active

| Plan | Status |
| --- | --- |
| `agent-eval-repair-recovery/` | Planning docs written 2026-08-30, not implemented — eval set v9 (strategist repair, error cases first) + first non-vacuous repair-recovery gate floor. |
| `career-track-expansion/` | Planning docs written, not implemented — 9 career profiles + mechanics checklist. |
| `hybrid-retrieval-ship/` | Planning docs written 2026-09-10, not implemented — ship the measured BM25+dense RRF hybrid as an opt-in claim-assembly retriever with its own eval gate. |
| `narrative-pathways/` | Planning docs written, not implemented — character sheet, pathway registry, knowledge map. |
| `resume-intake-onboarding/` | Implemented — RI-A…RI-F merged; running the enrichment tool and adopting a v5 taxonomy remains an operator action. |
| `scheduler-placement-quality/` | Partially complete — core spine (phases 01–03) merged; phases 04–05 gated on post-spine evidence. |

`generated-plans-ideas/` holds raw idea documents (.docx), not plans.

## Completed

Merged-to-`main` plans live in [`completed/`](completed/): the numbered
`phase-1`…`phase-9` roadmap plans, `phase-frontend-mvp`, the Loop MVP
backend/frontend plans and handoffs, `phase-loop-landing`, the calendar
reconciliation plan and handoff, and the plan folders
`animated-landing/`, `calendar-event-titles/`, `calendar-grid-rework/`,
`loop-grounding-rag/`, `loop-recruiter-readiness/`, `user-plan-direction/`,
and `ux-quality-pass/`.
