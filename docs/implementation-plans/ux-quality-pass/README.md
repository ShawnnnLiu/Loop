# UX Quality Pass — Four-Level Improvement Plan

Status: **idea backlog, not started.** These files record the improvement pass
proposed on 2026-07-03 from a four-dimension audit of the codebase (branch
`deleted-event-memory`). They are meant to be refined by the product owner
before any implementation. **No code has been changed.**

## The goal of this version

> "User experience is what I value with this version. I can increase cost
> ceiling as long as the product is incredibly smooth, reliable, friendly to
> the user and provides actual good guidance."

That reframes the audit findings. Earlier phases optimized for deterministic
safety and cost discipline; both are now strong (the harness is the most
mature layer in the repo). This pass optimizes for four user-perceived
qualities and treats token/model cost as a budget to spend, not minimize:

| UX value | What it means here | Where the work lives |
|---|---|---|
| **Smooth** | No dead-end screens, no invisible states, no "start over" as the only recovery | `01-loop-engineering.md` |
| **Reliable** | Provider hiccups never surface as stuck runs; prompt changes are measured before they ship | `04-harness-engineering.md` |
| **Friendly** | The words the user reads (explanations, reflections, banners) are warm, specific, and honest | `02-prompt-engineering.md` |
| **Good guidance** | Plans reflect the user's actual goal and history; the system remembers what it told them | `03-context-engineering.md` |

## Reading order = priority order

1. **`01-loop-engineering.md` — close the loops the user can feel.**
   The single worst UX failures today are control-loop dead-ends: a failed
   calendar write strands the run permanently in the SPA, a required replan is
   silently rendered as "Your week is scheduled," and the accountability system
   asks questions the user has no way to answer. Fixing these is worth more
   than any prompt improvement.
2. **`02-prompt-engineering.md` — upgrade the product's voice and first-try quality.**
   Few-shot exemplars, pinned sampling, structured repair, and (new under the
   raised cost ceiling) stronger models for the user-facing prose nodes.
3. **`03-context-engineering.md` — give the system memory and goal-awareness.**
   Persist reflection summaries, make replans aware of the prior plan, let the
   Planner see the user's goal, curate source claims, and turn on prompt
   caching.
4. **`04-harness-engineering.md` — make quality measurable and provider failures invisible.**
   Real-recording capture, CI-gated evals, semantic graders, adapter
   timeout/backoff, and a reader over the SQLite call log.

## Cost posture (changed from prior phases)

- **Spend where the user reads or waits:** model-tier upgrades for
  `ReflectionSummary` / `UserFacingExplanation` (and possibly the Planner) are
  on the table — see `02-prompt-engineering.md §6`. This requires an
  **axiom 09 (model tiering / pricing) amendment**, flagged there.
- **Free wins are still free:** prompt caching and input curation
  (`03-context-engineering.md §1, §5`) cut latency as much as cost — latency
  *is* UX — so they stay in scope even with a raised ceiling.
- **Never spend on the control plane:** nothing in this pass moves routing,
  validation, scheduling, approval, or calendar writes toward an LLM. Every
  proposal below keeps the project thesis: LLMs propose, deterministic
  infrastructure disposes.

## Ground rules carried into every file

- Docs/spec-first: any proposal that changes an object shape names the
  `docs/specs/*.schema.md` it must update first.
- Any proposal that touches an axiom says so explicitly in an
  **Axiom/spec implications** block; conflicts stop and go to the user
  (per `CLAUDE.md`).
- File pointers (`path:line`) were verified on 2026-07-03 on branch
  `deleted-event-memory`; line numbers will drift as the branch evolves —
  treat them as anchors, not gospel.
