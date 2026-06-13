"""Live smoke test for the Anthropic adapters (operator CLI, module-only).

Usage::

    uv run python -m agentic_calendar.tools.llm_smoke              # offline fixture mode
    uv run python -m agentic_calendar.tools.llm_smoke --live       # real API calls

Locked safeguards (user-approved 2026-06-10):

1. Default mode is fixture-only and fully offline. Live calls require BOTH
   ``--live`` and ``ANTHROPIC_API_KEY`` in the environment.
2. Hard cap of ``MAX_LIVE_CALLS`` (5) provider API calls per invocation,
   mirroring axiom 09's 5-calls/hour cost control. Not user-raisable.
3. Per-node ``max_tokens`` come from the adapter defaults (axiom 09 budgets).
4. Cumulative cost guard: before every call, a deterministic estimate
   (chars/4 input heuristic + the full output cap at the model's pricing)
   is added to the actual spend recorded so far; the run aborts before
   exceeding ``--max-cost-usd`` (default $0.25).
5. At most 2 SDK retries per call and 2 repair attempts (adapter defaults);
   exhaustion surfaces the typed reason code, never fabricated output.
6. Every call appends an LlmCallLog row (no raw content). Raw responses go
   to stdout only behind ``--debug-raw`` and are never written to disk.
   ``--calls-out`` writes only the log rows (hashes and counts).
7. This tool imports llm_nodes only — it cannot touch the scheduler,
   approval gate, or calendar writer (ADR-0006). Tests and CI never set the
   key; the suite makes zero network calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel

from agentic_calendar.common.clock import SystemClock
from agentic_calendar.common.ids import UuidIdGenerator
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import ValidationResult
from agentic_calendar.llm_nodes import (
    AnthropicMessagesTransport,
    AnthropicPlanner,
    AnthropicReflectionSummary,
    AnthropicStrategist,
    AnthropicTransport,
    AnthropicUserFacingExplanation,
    DeterministicReflectionSummary,
    DeterministicUserFacingExplanation,
    FixturePlanner,
    FixtureStrategist,
    InMemoryLlmCallLogStore,
    LLMNodeError,
)
from agentic_calendar.llm_nodes.anthropic_adapter import (
    EXPLANATION_CONFIG,
    PLANNER_CONFIG,
    REFLECTION_CONFIG,
    STRATEGIST_CONFIG,
    TransportResult,
)

#: Hard per-invocation cap on provider API calls (safeguard 2). Constant on
#: purpose — there is no flag to raise it.
MAX_LIVE_CALLS = 5

DEFAULT_MAX_COST_USD = 0.25


class SmokeGuardTripped(Exception):
    """A smoke safeguard (call cap or cost guard) refused the next call.

    Deliberately NOT a ``TransportError`` — the generation engine retries
    those, and a tripped guard must abort, not retry."""


class _GuardedTransport:
    """Wraps the real transport with the call cap and cumulative cost guard."""

    def __init__(
        self,
        inner: AnthropicTransport,
        *,
        store: InMemoryLlmCallLogStore,
        max_calls: int,
        max_cost_usd: float,
        pricing: dict[str, tuple[float, float]],
    ) -> None:
        self._inner = inner
        self._store = store
        self._max_calls = max_calls
        self._max_cost_usd = max_cost_usd
        self._pricing = pricing
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def complete(
        self,
        *,
        model_name: str,
        max_tokens: int,
        system: str,
        user_prompt: str,
        output_contract: type[BaseModel],
    ) -> TransportResult:
        if self._calls + 1 > self._max_calls:
            raise SmokeGuardTripped(
                f"call cap reached: this invocation already made {self._calls} "
                f"API calls (hard cap {self._max_calls})"
            )
        prices = self._pricing.get(model_name)
        if prices is None:
            raise SmokeGuardTripped(
                f"no pricing known for model {model_name!r}; refusing unbounded spend"
            )
        input_price, output_price = prices
        spent = sum(row.cost_estimate_usd for row in self._store.list_all())
        # chars/4 input heuristic + the full output cap: a deliberate
        # worst-case-output estimate so the guard errs toward aborting.
        estimated_next = (
            (len(system) + len(user_prompt)) // 4 * input_price + max_tokens * output_price
        ) / 1_000_000
        if spent + estimated_next > self._max_cost_usd:
            raise SmokeGuardTripped(
                f"cost guard: spent ~${spent:.4f} and the next call could add "
                f"~${estimated_next:.4f}, exceeding the ${self._max_cost_usd:.2f} budget"
            )
        self._calls += 1
        return self._inner.complete(
            model_name=model_name,
            max_tokens=max_tokens,
            system=system,
            user_prompt=user_prompt,
            output_contract=output_contract,
        )


# --- Fixed sample inputs (mirrors of the repo's valid fixtures) ---

_SAMPLE_USER_PROFILE: dict[str, object] = {
    "user_id": "user_smoke",
    "profile_version": "profile_smoke_001",
    "goal": "Backend SWE interview prep",
    "target_role": "Backend SWE",
    "target_companies": ["Meta", "Stripe"],
    "target_level": "new_grad",
    "timeline_weeks": 10,
    "weekly_hours": 8,
    "experience_level": "intermediate",
    "known_strengths": ["arrays", "hash maps"],
    "known_weaknesses": ["dynamic programming", "system design"],
    "preferred_session_length_min": 60,
    "max_session_length_min": 120,
    "deep_work_windows": [
        {"day": "Mon", "start": "18:00", "end": "21:00"},
        {"day": "Wed", "start": "19:00", "end": "21:30"},
    ],
    "hard_constraints": {
        "no_events_before": "08:00",
        "no_events_after": "22:30",
        "allow_weekends": True,
        "max_daily_study_min": 180,
        "min_break_between_deep_blocks_min": 30,
    },
    "preferences": {
        "prefer_evening_sessions": True,
        "prefer_weekend_long_blocks": False,
        "avoid_back_to_back_deep_work": True,
    },
    "motivation_profile_id": "mot_smoke",
    "created_at": "2026-06-10T12:00:00-07:00",
    "updated_at": "2026-06-10T12:00:00-07:00",
}

_SAMPLE_SYLLABUS: dict[str, object] = {
    "syllabus_version": "syl_003",
    "goal_summary": "Prepare for backend SWE interviews at Meta and Stripe over 10 weeks.",
    "modules": [
        {
            "module_id": "dp",
            "title": "Dynamic Programming",
            "priority": "high",
            "reason": "User listed DP as a weakness.",
            "target_outcomes": ["Recognize common DP state definitions"],
            "estimated_total_min": 720,
            "difficulty": 5,
            "source_claim_ids": ["claim_012"],
        },
        {
            "module_id": "api_design",
            "title": "API Design and Product-Oriented Backend Design",
            "priority": "medium",
            "reason": "Relevant for Stripe-style backend interviews.",
            "target_outcomes": ["Design clean API surfaces"],
            "estimated_total_min": 360,
            "difficulty": 4,
            "source_claim_ids": ["claim_024"],
        },
    ],
}

_SAMPLE_TASK_PLAN: dict[str, object] = {
    "plan_version": "plan_smoke_001",
    "tasks": [
        {
            "task_id": "dp_001",
            "module_id": "dp",
            "title": "Review DP state definitions",
            "dependencies": [],
            "estimated_duration_min": 60,
            "cognitive_load": 4,
            "category": "concept_review",
            "required_focus_level": "deep",
            "splittable": False,
        }
    ],
}

_SAMPLE_DRIFT_EVENT: dict[str, object] = {
    "drift_event_id": "drift_smoke_001",
    "plan_version": "plan_smoke_001",
    "drift_detected": True,
    "drift_type": "duration_underestimate",
    "reason_code": "DRIFT_DURATION_UNDERESTIMATE",
    "confidence": 0.82,
    "evidence": {
        "trigger_metric": "median_actual_vs_predicted_ratio",
        "trigger_value": 1.48,
        "threshold": 1.3,
        "sample_size": 6,
        "affected_categories": ["practice"],
    },
    "recommended_policy_action": "increase_duration_estimates_for_category",
    "detected_at": "2026-06-10T08:00:00-07:00",
}

_SAMPLE_VALIDATION_RESULT: dict[str, object] = {
    "run_id": "run_smoke_001",
    "artifact_type": "task_plan",
    "valid": True,
    "repairable": False,
    "reason_code": None,
    "violations": [],
    "repair_attempt": 0,
    "max_repair_attempts": 2,
    "next_action": "scheduler",
}


def sample_fixture_inputs() -> tuple[UserProfile, SyllabusUnits, TaskPlan]:
    """The validated canned smoke inputs, for reuse by other operator CLIs.

    ``run_cycle --llm fixture`` builds its fixture node bundle from these so
    the demo loop and the smoke exercise the same sample data.
    """
    return (
        UserProfile.model_validate(_SAMPLE_USER_PROFILE),
        SyllabusUnits.model_validate(_SAMPLE_SYLLABUS),
        TaskPlan.model_validate(_SAMPLE_TASK_PLAN),
    )


def _run_fixture_mode() -> int:
    """Offline default: prove the wiring with the deterministic nodes."""
    profile = UserProfile.model_validate(_SAMPLE_USER_PROFILE)
    syllabus = SyllabusUnits.model_validate(_SAMPLE_SYLLABUS)
    drift = DriftEvent.model_validate(_SAMPLE_DRIFT_EVENT)
    validation = ValidationResult.model_validate(_SAMPLE_VALIDATION_RESULT)

    strategist = FixtureStrategist({"Backend SWE": syllabus})
    planner = FixturePlanner({"syl_003": TaskPlan.model_validate(_SAMPLE_TASK_PLAN)})
    reflection = DeterministicReflectionSummary()
    explanation = DeterministicUserFacingExplanation()

    out_syllabus = strategist.run(run_id="run_smoke_001", user_profile=profile)
    out_plan = planner.run(run_id="run_smoke_001", syllabus=out_syllabus)
    out_reflection = reflection.run(
        run_id="run_smoke_001", drift_events=[drift], completion_rate=0.7
    )
    out_explanation = explanation.run(
        run_id="run_smoke_001", validation_result=validation
    )

    print("fixture mode (offline, no API calls):")
    print(f"  strategist  ok ({len(out_syllabus.modules)} modules)")
    print(f"  planner     ok ({len(out_plan.tasks)} tasks)")
    print(f"  reflection  ok ({len(out_reflection.detail)} detail lines)")
    print(f"  explanation ok ({len(out_explanation.detail)} detail lines)")
    print("Pass --live (with ANTHROPIC_API_KEY set) for real API calls.")
    return 0


def _run_live_mode(
    transport_factory: Callable[[], AnthropicTransport],
    *,
    max_cost_usd: float,
    debug_raw: bool,
    calls_out: Path | None,
) -> int:
    store = InMemoryLlmCallLogStore()
    clock = SystemClock()
    ids = UuidIdGenerator()
    sink: Callable[[str], None] | None = None
    if debug_raw:

        def sink(raw: str) -> None:
            print(f"--- raw response (not persisted) ---\n{raw}\n---")

    pricing = {
        config.model_name: (config.input_price_per_mtok, config.output_price_per_mtok)
        for config in (STRATEGIST_CONFIG, PLANNER_CONFIG, REFLECTION_CONFIG, EXPLANATION_CONFIG)
    }
    transport = _GuardedTransport(
        transport_factory(),
        store=store,
        max_calls=MAX_LIVE_CALLS,
        max_cost_usd=max_cost_usd,
        pricing=pricing,
    )
    profile = UserProfile.model_validate(_SAMPLE_USER_PROFILE)
    syllabus = SyllabusUnits.model_validate(_SAMPLE_SYLLABUS)
    drift = DriftEvent.model_validate(_SAMPLE_DRIFT_EVENT)
    validation = ValidationResult.model_validate(_SAMPLE_VALIDATION_RESULT)

    strategist = AnthropicStrategist(
        transport=transport, store=store, clock=clock, id_generator=ids, debug_raw_sink=sink
    )
    planner = AnthropicPlanner(
        transport=transport, store=store, clock=clock, id_generator=ids, debug_raw_sink=sink
    )
    reflection = AnthropicReflectionSummary(
        transport=transport, store=store, clock=clock, id_generator=ids, debug_raw_sink=sink
    )
    explanation = AnthropicUserFacingExplanation(
        transport=transport, store=store, clock=clock, id_generator=ids, debug_raw_sink=sink
    )

    def _strategist() -> str:
        result = strategist.run(run_id="run_smoke_001", user_profile=profile)
        return f"{len(result.modules)} modules"

    def _planner() -> str:
        result = planner.run(run_id="run_smoke_001", syllabus=syllabus)
        return f"{len(result.tasks)} tasks"

    def _reflection() -> str:
        result = reflection.run(
            run_id="run_smoke_001", drift_events=[drift], completion_rate=0.7
        )
        return f"{len(result.detail)} detail lines"

    def _explanation() -> str:
        result = explanation.run(run_id="run_smoke_001", validation_result=validation)
        return f"{len(result.detail)} detail lines"

    runs: list[tuple[str, Callable[[], str]]] = [
        ("strategist", _strategist),
        ("planner", _planner),
        ("reflection", _reflection),
        ("explanation", _explanation),
    ]

    failures: list[str] = []
    print(f"live mode: cap {MAX_LIVE_CALLS} calls, budget ${max_cost_usd:.2f}")
    for name, invoke in runs:
        try:
            summary = invoke()
        except SmokeGuardTripped as guard:
            print(f"  {name:<11} ABORTED — {guard}")
            failures.append(name)
            break
        except LLMNodeError as exc:
            code = getattr(exc, "reason_code", None)
            code_text = code.value if code is not None else "n/a"
            print(f"  {name:<11} FAILED — reason_code={code_text}")
            failures.append(name)
            continue
        print(f"  {name:<11} ok ({summary})")

    rows = store.list_all()
    spent = sum(row.cost_estimate_usd for row in rows)
    in_tok = sum(row.input_tokens for row in rows)
    out_tok = sum(row.output_tokens for row in rows)
    print(
        f"calls={transport.calls} input_tokens={in_tok} output_tokens={out_tok} "
        f"estimated_cost=${spent:.4f} (estimate, axiom 09 disclosure)"
    )
    if calls_out is not None:
        text = json.dumps(
            [row.model_dump(mode="json") for row in rows], indent=2, sort_keys=True
        )
        calls_out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {len(rows)} llm_call_log rows (no raw content) to {calls_out}")
    return 1 if failures else 0


def main(
    argv: Sequence[str] | None = None,
    transport_factory: Callable[[], AnthropicTransport] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="llm_smoke",
        description="Smoke-test the LLM adapters. Offline fixture mode by default.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=f"Make real API calls (requires ANTHROPIC_API_KEY; cap {MAX_LIVE_CALLS} calls).",
    )
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=DEFAULT_MAX_COST_USD,
        help=f"Abort before estimated spend exceeds this (default {DEFAULT_MAX_COST_USD}).",
    )
    parser.add_argument(
        "--debug-raw",
        action="store_true",
        help="Print raw model responses to stdout (never persisted).",
    )
    parser.add_argument(
        "--calls-out",
        type=Path,
        default=None,
        help="Write the llm_call_log rows (hashes/counts only) as JSON.",
    )
    args = parser.parse_args(argv)

    if not args.live:
        return _run_fixture_mode()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "error: --live requires ANTHROPIC_API_KEY in the environment "
            "(the key is never read from files or arguments)",
            file=sys.stderr,
        )
        return 1
    if args.max_cost_usd <= 0:
        print("error: --max-cost-usd must be positive", file=sys.stderr)
        return 1

    factory = transport_factory or AnthropicMessagesTransport
    return _run_live_mode(
        factory,
        max_cost_usd=args.max_cost_usd,
        debug_raw=args.debug_raw,
        calls_out=args.calls_out,
    )


if __name__ == "__main__":
    raise SystemExit(main())
