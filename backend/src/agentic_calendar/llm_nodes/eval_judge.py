"""Tier-2 LLM-judge grading of prose recordings (UX pass C2).

A deliberate, axiom-scoped decision (axiom 22): axiom 01 allows exactly four
LLM *workflow* node classes — this judge is NOT a node. It runs only inside
offline eval tooling (the capture CLI's orbit), grades already-recorded prose
against the voice rubric, and its scores are advisory numbers in the eval
report. They are never gates and never runtime signals; nothing in ``app/``
imports this module.

The judge shares the adapter transport (so the capture tool's call cap and
cost guard bound it too) but deliberately NOT the generation engine: engine
calls append LlmCallLog rows keyed by workflow node names, and the judge must
stay visibly outside that taxonomy.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .anthropic_adapter import AdapterConfig, AnthropicTransport, TransportError
from .call_log import LlmNodeName
from .eval import EvalRecording, EvalSet, JudgeScore, _first_valid_attempt

#: Sonnet-tier judge: cheap enough to run per prose case, strong enough to
#: hold a rubric. Pricing per the Claude model table (sticker, not intro).
JUDGE_CONFIG = AdapterConfig(
    model_name="claude-sonnet-5",
    prompt_version="judge-v1-2026-07-04",
    max_tokens=256,
    input_price_per_mtok=3.00,
    output_price_per_mtok=15.00,
)

_JUDGE_SYSTEM = (
    "You grade one short coaching message from a study-planning product. "
    "The audience is a person preparing for job interviews; the product's "
    "voice is a supportive coach, never a clinician.\n\n"
    "Score each dimension from 1 (poor) to 5 (excellent):\n"
    "1. tone — warm and supportive; describes behavior only, never attaches "
    "psychological or identity labels to the person.\n"
    "2. specificity — names the person's actual situation (which tasks, what "
    "pattern) instead of generic filler that could apply to anyone.\n"
    "3. actionability — leaves the person with one concrete next step they "
    "could take today.\n\n"
    "Judge only the message given. Return only the structured object."
)

_PROSE_NODES = (LlmNodeName.REFLECTION_SUMMARY, LlmNodeName.USER_FACING_EXPLANATION)


def _judge_one(
    transport: AnthropicTransport,
    config: AdapterConfig,
    *,
    description: str,
    summary: str,
    detail: list[str],
) -> JudgeScore | None:
    """One bounded judge call; None when the judge itself misbehaves.

    A failed judge call must never fail the capture run — the scores are
    advisory. The caller reports how many cases went unjudged."""
    prose = summary if not detail else summary + "\n" + "\n".join(detail)
    user_prompt = (
        f"Context (what triggered the message): {description or 'not specified'}\n\n"
        f"Message to grade:\n{prose}"
    )
    for _ in range(config.max_sdk_retries + 1):
        try:
            result = transport.complete(
                model_name=config.model_name,
                max_tokens=config.max_tokens,
                system=_JUDGE_SYSTEM,
                user_prompt=user_prompt,
                output_contract=JudgeScore,
                timeout_seconds=config.timeout_seconds,
            )
        except TransportError as exc:
            if not exc.retryable:
                return None
            continue
        if result.payload is None:
            continue
        try:
            return JudgeScore.model_validate(result.payload)
        except ValidationError:
            continue
    return None


def judge_recording(
    eval_set: EvalSet,
    recording: EvalRecording,
    *,
    transport: AnthropicTransport,
    config: AdapterConfig = JUDGE_CONFIG,
) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Score every prose case's first VALID recorded attempt.

    Returns ``(scores_by_case_id, unjudged_case_ids)``. Cases whose recording
    never produced contract-valid prose are skipped (there is nothing a user
    would have seen); judge misbehavior lands the case in ``unjudged`` so the
    capture tool can report the gap instead of silently narrowing coverage.
    """
    scores: dict[str, dict[str, int]] = {}
    unjudged: list[str] = []
    for case in eval_set.cases:
        if case.node not in _PROSE_NODES:
            continue
        attempts = recording.outputs.get(case.case_id, [])
        _, validated = _first_valid_attempt(case, attempts)
        if validated is None:
            continue
        payload: dict[str, Any] = json.loads(validated.model_dump_json())
        score = _judge_one(
            transport,
            config,
            description=case.description,
            summary=str(payload.get("summary", "")),
            detail=[str(line) for line in payload.get("detail", [])],
        )
        if score is None:
            unjudged.append(case.case_id)
        else:
            scores[case.case_id] = score.model_dump()
    return scores, unjudged
