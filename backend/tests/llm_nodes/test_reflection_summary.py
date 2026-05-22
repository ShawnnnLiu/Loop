"""Tests for the Phase 1 reflection-summary stub."""

from __future__ import annotations

import pytest

from agentic_calendar.llm_nodes import StubReflectionSummary


def test_stub_raises_until_phase_4() -> None:
    node = StubReflectionSummary()
    with pytest.raises(NotImplementedError) as exc_info:
        node.run(run_id="r")
    assert "Phase 4" in str(exc_info.value)
