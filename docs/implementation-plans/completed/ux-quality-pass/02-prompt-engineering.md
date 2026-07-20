# 02 · Prompt Engineering — Upgrade the Product's Voice and First-Try Quality

Priority: **second.** Two distinct UX payoffs live here: (a) the words the
user actually reads — reflections, explanations — are the product's voice and
today run on the smallest model with the tersest prompts; (b) fewer repair
retries means faster generation, and generation latency is the single longest
wait in the product.

Where everything lives: **all real prompts are in one file**,
`backend/src/agentic_calendar/llm_nodes/anthropic_adapter.py`. The four node
modules (`strategist.py`, `planner.py`, `reflection_summary.py`,
`user_facing_explanation.py`) are deterministic fixtures + output contracts,
not prompt sources. The design pattern is documented at
`anthropic_adapter.py:523-528`: role → why → enumerated rules mapped 1:1 to
the deterministic validators → self-verify step; field shape is delegated to
the API's `json_schema` structured-output path (`:134-144`) and re-validated
at the boundary (`:437`).

What already works (do not disturb): structured outputs + boundary
re-validation, the prompt-injection fencing of the résumé (`:548-551`,
`:665-669`), `prompt_version` + `prompt_hash` stamped on every call-log row
(`:185, :211-238, :337, :499-517`), and the psych-label denylist post-validator
backing the prose prompts (`reflection_summary.py:37-52`, `_scan_prose`
`:605-608`).

---

## 1. Add few-shot exemplars to Strategist and Planner

**Problem (user experience).** Not one prompt in the system contains a worked
example — verified across all four system prompts and all user-prompt
builders. The two structured nodes rely on prose rule lists
(`_STRATEGIST_SYSTEM` `:530-552`, `_PLANNER_SYSTEM` `:554-577`) plus the
enforced schema. Every invariant miss (duplicate `task_id`, cycle in
`dependencies`, uncovered high-priority module) costs a full repair round trip
— i.e., **seconds of user-visible generation time and a full second model
call**. `docs/axioms/22-llm-evaluation-and-observability.md:40` already names
"adding a schema example" as the canonical improvement, citing a hypothetical
78% → 96% schema-validity jump.

**Proposal.**
- Append one compact, canonical valid exemplar to each structured system
  prompt: for the Planner, a 3-task mini-plan demonstrating a correct
  `dependencies` DAG, module coverage, and the *absence* of
  `prerequisites_met`; for the Strategist, a 2-module mini-syllabus where the
  company-specific module carries `source_claim_ids`.
- Keep exemplars deliberately small (the goal is anchoring invariants, not
  padding tokens) and mark them clearly as illustrative shape, not content to
  copy.
- Bump `prompt_version` constants (`:211-238`) and measure before/after with
  the eval harness — this is the natural first experiment for
  `04-harness-engineering.md §1`.

**Why.** Highest-expected-value prompt change in the repo: it attacks
generation latency (fewer repair rounds) and first-try plan quality
simultaneously. With the raised cost ceiling, exemplar tokens are cheap; the
repair round trips they prevent are the expensive part anyway.

**Touchpoints.** `anthropic_adapter.py:530-577` (both system prompts),
`:211-238` (version bumps), `tests/llm_nodes/test_anthropic_adapter.py`
(scaffolding assertions), `backend/evalsets/` (before/after recordings).

**Axiom/spec implications.** None — axiom 22 anticipates exactly this and
requires the before/after report.

---

## 2. Rewrite the prose-node prompts as the product's voice

**Problem (user experience).** `_REFLECTION_SYSTEM` (`:579-589`) and
`_EXPLANATION_SYSTEM` (`:591-602`) are three rules each with guidance no
stronger than "Keep it brief and supportive" — no tone exemplar, no length
bound, no structure guidance. Their safety net is a fixed **12-word**
psych-label denylist (`reflection_summary.py:37-52`); any identity-labeling
phrasing outside those stems passes both prompt and post-validator. These two
nodes produce nearly all the sentences a user reads from the LLM; they are
currently the least-engineered prompts in the system.

**Proposal.**
- Give each prose node a real voice spec: audience, tone ("coach, not
  clinician"), length bound, structure (what happened → what it suggests →
  one concrete next step), and 1-2 short exemplar outputs demonstrating the
  tone — including a *negative* exemplar of the labeling failure mode the
  denylist guards.
- For explanations specifically: require that the prose name the typed
  `reason_code`'s plain-language meaning and the user's available next action
  (this pairs with `01-loop-engineering.md §5`, which puts these explanations
  in front of users at failure time).
- Broaden the denylist review while in there (it stays deterministic; the
  prompt exemplars reduce how often it fires).

**Why.** "Friendly" is decided by these two prompts more than by anything
else in the repo. The current investment is inverted relative to user
exposure: the prompts users never see (Strategist/Planner) got the careful
engineering; the ones they read got three lines.

**Touchpoints.** `anthropic_adapter.py:579-602`, `reflection_summary.py:37-52`
(denylist), version bumps `:229-238`, prose-node eval cases in
`backend/evalsets/eval_set_v1.json` (all rubric surfaces:
`required_substrings` + denylist, `eval.py:203-213`).

**Axiom/spec implications.** Axiom 07's behavior-not-identity rule is
strengthened, not weakened. Keep "prompt wording is not a test oracle" —
assertions stay on scaffolding + denylist + rubric, never exact phrasing.

---

## 3. Pin sampling parameters

**Problem (user experience).** No `temperature`, `top_p`, or `stop_sequences`
are set anywhere — `messages.create` passes only `model`, `max_tokens`,
`system`, `messages`, `output_config` (`anthropic_adapter.py:138-144`).
Structured-node output variance is pure downside here: it adds repair-round
lottery to generation time, and it muddies every before/after eval comparison
this pass depends on.

**Proposal.** Set `temperature` explicitly per node in `AdapterConfig`
(`:183-199`): low/zero for Strategist and Planner (determinism is a feature —
same inputs should propose the same plan), modest (e.g. default or slightly
reduced) for the prose nodes where a little variation reads as natural.
Record the value in the call log row if worth auditing (schema change — see
`docs/specs/llm-call-log.schema.md` first).

**Why.** Cheap, immediate reliability win, and a precondition for trusting
eval deltas (`04-harness-engineering.md §1-2`).

**Touchpoints.** `anthropic_adapter.py:138-144` (transport), `:183-238`
(config + per-node values), optionally `llm_nodes/call_log.py:50-74` +
`docs/specs/llm-call-log.schema.md` + `make schemas` if logging it.

**Axiom/spec implications.** Only the optional call-log field (spec-first
rule applies).

---

## 4. Unify the two repair channels on structured feedback

**Problem (user experience).** Repair quality decides whether a marginal
generation recovers in one extra round or exhausts its budget and dumps the
user at `ERROR_REQUIRES_USER`. The two channels are inconsistent:

- The Planner's *inbound* repair path is well-engineered: the failed
  `ValidationResult` (typed `reason_code` + violations) is embedded as
  canonical JSON (`anthropic_adapter.py:752-765`).
- The engine-internal loop is not: it appends the **raw
  `str(pydantic.ValidationError)`** (`:453`) or, for unparseable output, the
  single fixed sentence "the response could not be parsed into the target
  schema" (`:434`) — no field hints, no schema echo, phrasing optimized for
  Python tracebacks rather than model repair.

**Proposal.** Build one repair-context formatter used by both channels:
typed violation list (field path → constraint → offending value where safe),
plus for the unparseable case a one-line reminder of the top-level required
keys. Keep the existing bound (`max_repair_attempts ≤ 2`, `:191`) and the
"rejected by deterministic validation" marker the tests assert on
(`tests/llm_nodes/test_anthropic_adapter.py:227,240,500`).

**Why.** Directly converts repair rounds from coin flips into targeted fixes;
each avoided exhaustion is one fewer dead-end screen.

**Touchpoints.** `anthropic_adapter.py:299-323` (engine loop), `:434`, `:453`,
`:752-765`; `validation/` violation shapes are already structured — reuse,
don't reinvent.

**Axiom/spec implications.** None; repair stays bounded and deterministic on
the control side.

---

## 5. Tie `prompt_version` to the prompt bytes

**Problem (user experience — indirect but foundational).** `prompt_version`
is a hand-maintained constant (`strategist-v2-2026-06-23` etc., `:211-238`)
with no linkage to the actual prompt text. An edit without a manual bump
silently mislabels every eval comparison and every call-log row — invisibly
corrupting exactly the measurement loop this pass relies on. (`prompt_hash`
can't serve: it hashes system+user content together, `:337`.)

**Proposal.** A unit test that asserts a SHA-256 of each system-prompt
constant against a pinned value stored next to the version string; changing a
prompt forces the test to fail until both hash and version are updated
together. (Alternative: derive the version suffix from the hash — rejected
because human-readable dated versions are more useful in eval reports.)

**Why.** Every quality claim this pass makes ("the new planner prompt lifted
first-try validity from X to Y") is only as trustworthy as this linkage.

**Touchpoints.** `anthropic_adapter.py:211-238, 530-602`, new test in
`tests/llm_nodes/`.

**Axiom/spec implications.** None.

---

## 6. Model-tier upgrades for user-facing quality (uses the raised cost ceiling)

**Problem (user experience).** Current tiering (`:202-238`, per axiom 09):
Strategist `claude-opus-4-8`; **Planner, Reflection, Explanation all
`claude-haiku-4-5`**. Cost discipline put the smallest model on: (a) the node
that decomposes the syllabus into every task the user will actually schedule
and read, and (b) both nodes that write the product's user-facing sentences.

**Proposal.** With the explicit new cost posture:
- **Planner → Sonnet-tier** (e.g. `claude-sonnet-5`): better task titling,
  saner dependency structures, fewer repair rounds on the invariant-heaviest
  contract in the system.
- **Reflection + Explanation → Sonnet-tier**: warmer, more specific prose for
  a few hundred extra tokens per event. These calls are rare (drift events,
  repair exhaustion) — the absolute cost delta is small; the perceived-quality
  delta is where the user's trust lives.
- Strategist stays Opus-tier.
- Run each swap as an eval experiment (`04-harness-engineering.md §1`):
  recordings before/after, same eval set, `compare_reports`
  (`llm_nodes/eval.py:344-366`) keyed on the version bump.

**Why.** This is the single most direct way to spend the raised ceiling on
"actual good guidance." Model choice dominates prompt tweaks for prose
quality at this scale.

**Touchpoints.** `anthropic_adapter.py:211-238` (model ids + pricing
constants), **`docs/axioms/09-*` (model tiering / pricing) must be amended
first** — this is a deliberate axiom change, stop-and-confirm per
`CLAUDE.md`. Also update cost estimates fed to
`AdapterConfig.estimate_cost_usd` (`:194-199`).

**Axiom/spec implications.** **Axiom 09 amendment required.** Pricing plan
assumptions (the $39/$33 figures from the Phase 8 follow-up) should be
re-checked against the new per-run cost envelope.

**Open questions.** Whether the Planner upgrade is needed at all once §1
(few-shot) lands — recommended order: few-shot first, measure, then decide
the Planner tier with data.
