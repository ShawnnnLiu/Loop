# UX Quality Pass — Four-Level Improvement Plan

Status: **IMPLEMENTED** (branch `ux-quality-pass`, 2026-07-04 → 2026-07-05).
These files record the improvement pass proposed on 2026-07-03 from a
four-dimension audit of the codebase. All four tracks shipped; per-increment
specs, the load-bearing deviations, and the capture choreography live in
`HANDOFF.md`, and the session-by-session record in `SESSION-SPLIT.md`.

## Outcome (what shipped, per file)

- **`01-loop-engineering.md` — shipped in full (B1–B5, commits `ada4658`…`f75cf09`).**
  Failed writes now recover end to end (rollback/retry signals + `/api/rollback`
  + `/api/retry-write` + the 3-option Approval card), a required replan is
  surfaced (Week banner, ask-each-time recovery picker, Today "needs attention"
  chip), recommitment and the weekly check-in are answerable (B3), the drift
  classifier is fed its full input (B4), and reflections/explanations persist
  and replay (B5). All three recovery flows were verified in a real browser
  (headless Chrome over CDP against the keyless dev server, 2026-07-05).
  Post-audit hardening: a failed delete-only *drop* write — which has no
  retry/rollback path — now renders an honest "build a new plan" card instead
  of dead-ending the Approval screen, and a rolled-back run renders as a
  *closed* plan attempt, never as "written and confirmed".
- **`02-prompt-engineering.md` — shipped except §3 (A2, D1a, D2, D3).**
  Prompt caching with byte-pinned prompt↔version tests (extended post-audit to
  pin the full rendered prompts, not just system prompts), few-shot exemplars +
  unified typed repair formatting, prose voice specs (measured: judge tone
  3.60→5.00, actionability 3.60→4.60 vs baseline; the target
  `explanation_repair_exhausted` case went tone 2→5), and the Sonnet-tier swap
  for Planner/Reflection/Explanation under the amended axiom 09.
  **Deviation:** §3 temperature pinning is deliberately NOT implemented —
  sampling is API-pinned on every target tier; comparability rests on
  prompt-byte pinning instead.
- **`03-context-engineering.md` — shipped in full (A2, D1b, D2, D4).**
  Planner goal block (typed profile fields only), claim curation behind a
  `claim_curation` tuning section (per-source-host cap — company identity is
  not a contract field), reflection-memory feedback into the reflection node
  and the replan Planner, prior-plan anchoring on recovery replans
  (planner-v5) and the deterministic old→new plan diff surfaced on Week and
  Approval. **Deviation:** the cache breakpoint sits on the base user block,
  not the system prompt (provider minimum).
- **`04-harness-engineering.md` — shipped in full (C1–C3).**
  Adapter timeout/backoff/typed provider-error taxonomy, real-recording
  capture + eval set v2 + Tier-1/Tier-2 graders, `make eval-gate` in CI over
  every committed v2 recording (axiom 22 amendment), call-log readers, and —
  post-audit — cache-tier-aware cost accounting (5m-TTL write 1.25×, read
  0.1×) so `cost_estimate_usd` no longer understates cached calls.
  Measured captures: baseline / fewshot / voice, ≈$0.14–0.16 per capture run
  over the 11-case eval set, schema validity and rubric rates 1.0 throughout.

A whole-branch bs-detector audit (2026-07-05) closed the pass: 7 findings
(2 HIGH), all fixed on-branch — see the audit-fix commits and the corrected
C1 narrative note in `HANDOFF.md`'s deviations list.

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
