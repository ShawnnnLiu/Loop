"""Tests for the ``LlmCallLog`` contract and append-only store."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.llm_nodes.call_log import (
    InMemoryLlmCallLogStore,
    LlmCallLog,
    LlmCallLogAlreadyExistsError,
    LlmCallLogStore,
    LlmNodeName,
    ValidationOutcome,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "llm_call_log"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    log = LlmCallLog.model_validate(payload)
    assert log.llm_call_log_id == payload["llm_call_log_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        LlmCallLog.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def _minimal_payload(log_id: str = "llmcall_t_001", run_id: str = "run_t") -> dict[str, object]:
    return {
        "llm_call_log_id": log_id,
        "run_id": run_id,
        "node": "planner",
        "prompt_version": "planner-2026-06-01",
        "model_name": "claude-haiku-4-5-20251001",
        "attempt": 0,
        "input_tokens": 6000,
        "output_tokens": 7000,
        "cost_estimate_usd": 0.005,
        "latency_ms": 9000,
        "validation_outcome": "pass",
        "created_at": "2026-06-10T14:05:00-07:00",
    }


def test_defaults_applied() -> None:
    """Optional fields default to null/0/false on a minimal valid entry."""
    log = LlmCallLog.model_validate(_minimal_payload())
    assert log.plan_version is None
    assert log.reason_code is None
    assert log.sdk_retry == 0
    assert log.cache_creation_tokens == 0
    assert log.cache_read_tokens == 0
    assert log.cache_hit is False
    assert log.truncated is False
    assert log.refusal is False
    assert log.prompt_hash is None
    assert log.response_hash is None
    assert log.node is LlmNodeName.PLANNER
    assert log.validation_outcome is ValidationOutcome.PASS


def test_contract_has_no_raw_content_fields() -> None:
    """Privacy (axiom 22): the record can carry hashes and counts, never text.

    ``extra="forbid"`` rejects unknown fields (fixture
    ``raw_prompt_text_field``); this guards against a raw-content field being
    *added to the contract* later without tripping a review."""
    field_names = set(LlmCallLog.model_fields)
    forbidden = {"prompt", "response", "prompt_text", "response_text", "messages", "content"}
    assert not (field_names & forbidden)


# --- Store ---


def test_store_satisfies_protocol() -> None:
    assert isinstance(InMemoryLlmCallLogStore(), LlmCallLogStore)


def test_append_and_list_for_run_preserves_order() -> None:
    store = InMemoryLlmCallLogStore()
    a = LlmCallLog.model_validate(_minimal_payload("llmcall_a", "run_1"))
    b = LlmCallLog.model_validate(_minimal_payload("llmcall_b", "run_2"))
    c = LlmCallLog.model_validate(_minimal_payload("llmcall_c", "run_1"))
    store.append(a)
    store.append(b)
    store.append(c)
    assert [log.llm_call_log_id for log in store.list_for_run("run_1")] == [
        "llmcall_a",
        "llmcall_c",
    ]
    assert [log.llm_call_log_id for log in store.list_all()] == [
        "llmcall_a",
        "llmcall_b",
        "llmcall_c",
    ]


def test_append_rejects_duplicate_id() -> None:
    store = InMemoryLlmCallLogStore()
    log = LlmCallLog.model_validate(_minimal_payload("llmcall_dup"))
    store.append(log)
    with pytest.raises(LlmCallLogAlreadyExistsError):
        store.append(log)
    assert len(store.list_all()) == 1


def test_list_for_unknown_run_is_empty() -> None:
    store = InMemoryLlmCallLogStore()
    assert store.list_for_run("run_missing") == []
