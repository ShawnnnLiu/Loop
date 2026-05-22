"""Smoke test: the package imports and exposes a version string.

This exists so ``uv run pytest`` returns a passing run before any business
logic lands. As regions get implemented, their own ``tests/<region>/`` suites
take over.
"""

from __future__ import annotations

import importlib

import pytest

import agentic_calendar

PHASE_1_PACKAGES = (
    "agentic_calendar.common",
    "agentic_calendar.contracts",
    "agentic_calendar.llm_nodes",
    "agentic_calendar.planning",
    "agentic_calendar.prerequisites",
    "agentic_calendar.scheduler",
    "agentic_calendar.supervisor",
    "agentic_calendar.tools",
    "agentic_calendar.validation",
)


def test_package_version_is_string() -> None:
    assert isinstance(agentic_calendar.__version__, str)
    assert agentic_calendar.__version__.count(".") == 2


@pytest.mark.parametrize("module_name", PHASE_1_PACKAGES)
def test_phase_1_packages_importable(module_name: str) -> None:
    """Every Phase 1 region must import cleanly even before logic lands."""
    module = importlib.import_module(module_name)
    assert module is not None
