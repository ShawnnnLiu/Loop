"""Tests for the list-templates CLI (Phase 5c)."""

from __future__ import annotations

import json

import pytest

from agentic_calendar.contracts.milestone_template import GoalClass
from agentic_calendar.tools.list_templates import main


def test_lists_all_templates(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    for goal_class in GoalClass:
        assert goal_class.value in out


def test_goal_class_filter(capsys: pytest.CaptureFixture[str]) -> None:
    selected = GoalClass.CAREER_TRANSITION
    rc = main(["--goal-class", selected.value])
    assert rc == 0
    out = capsys.readouterr().out
    assert selected.value in out
    for other in GoalClass:
        if other is not selected:
            assert other.value not in out


def test_unknown_goal_class_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--goal-class", "nope"])
    assert rc == 1
    assert "unknown goal class" in capsys.readouterr().err


def test_json_output_is_valid(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert len(payload) == len(GoalClass)
    assert {t["goal_class"] for t in payload} == {g.value for g in GoalClass}
