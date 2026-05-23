"""Structural tests for the schedule visualizer.

The visualizer is a renderer, not a planning component — pixel-perfect
snapshot testing would be brittle and add no real safety. These tests pin
the contracts that downstream readers and tools rely on:

* output is deterministic (no clock, no I/O, no randomness);
* every scheduled task surfaces in the HTML so it's visible;
* every unscheduled task surfaces with its typed ``reason_code``;
* the no-calendar-write invariant holds — no ``calendar_event_id`` leaks
  into the rendered file (Phase 1 is draft-only, axiom 06);
* the CLI's three modes (list / render / write file) all work.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.scheduler import schedule
from agentic_calendar.tools.visualize import (
    SCENARIOS,
    main,
    render_schedule_html,
)


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_every_scenario_renders_non_empty_svg(scenario_name: str) -> None:
    """Sanity: every built-in scenario produces a valid-looking HTML+SVG."""
    inp = SCENARIOS[scenario_name].build()
    out = schedule(inp)
    html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    assert html, "render returned empty string"
    assert "<svg" in html, "no SVG tag found"
    assert "<!doctype html>" in html, "missing HTML doctype"
    assert html.count("</html>") == 1, "HTML document not closed exactly once"


def test_render_is_deterministic() -> None:
    """Identical inputs must produce a byte-identical HTML string.

    Pins the 'no clock, no I/O, no randomness' contract documented in the
    module docstring. Without this, two consecutive runs could diverge and
    nothing in this codebase would catch it.
    """
    inp = SCENARIOS["success"].build()
    out = schedule(inp)
    first = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    second = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    assert first == second


def test_scheduled_task_ids_all_present_in_html() -> None:
    """Every scheduled task_id must appear in the HTML so the user sees it.

    Uses the ``success`` scenario because it places at least one task.
    """
    inp = SCENARIOS["success"].build()
    out = schedule(inp)
    assert out.scheduled_tasks, "scenario must produce at least one placement"
    html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    for st in out.scheduled_tasks:
        assert st.task_id in html, f"missing task_id {st.task_id!r} in HTML"


@pytest.mark.parametrize(
    "scenario_name", ["fragmented", "over_capacity", "task_too_long", "deep_work_blocked"]
)
def test_unscheduled_reason_codes_surface_in_html(scenario_name: str) -> None:
    """Every unscheduled task's typed reason_code must appear in the HTML."""
    inp = SCENARIOS[scenario_name].build()
    out = schedule(inp)
    assert out.unscheduled_tasks, (
        f"scenario {scenario_name} should produce at least one unscheduled task"
    )
    html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    for u in out.unscheduled_tasks:
        assert u.reason_code.value in html, (
            f"missing reason_code {u.reason_code.value!r} in HTML"
        )


def test_deep_work_band_marker_present_when_windows_configured() -> None:
    """When the policy enables deep-work windows, the SVG must include the
    band marker so a reader can visually verify deep-task placement."""
    inp = SCENARIOS["success"].build()  # success has Mon+Tue deep windows
    out = schedule(inp)
    html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    assert "deep-work-band" in html, "expected deep-work-band class in SVG"


def test_no_deep_work_band_when_disabled() -> None:
    """When ``respect_deep_work_windows`` is off, no band rect should render."""
    inp = SCENARIOS["fragmented"].build()  # respect_deep_work_windows=False
    out = schedule(inp)
    html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    # The legend chip still mentions the class, so we check the SVG body
    # specifically: there must be no <rect class="deep-work-band" ...>.
    assert '<rect class="deep-work-band"' not in html


def test_no_calendar_event_id_leaks_into_html() -> None:
    """Phase 1 invariant (axiom 06): the rendered HTML must not contain
    ``calendar_event_id`` anywhere.

    The Scheduler emits ``DRAFT_ONLY`` placements; this is the last
    chance to catch a regression before a real reader sees a 'real-looking'
    event id.
    """
    for name in sorted(SCENARIOS):
        inp = SCENARIOS[name].build()
        out = schedule(inp)
        html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
        assert "calendar_event_id" not in html, (
            f"calendar_event_id leaked into HTML for scenario {name!r}"
        )


def test_busy_block_rendered_when_free_busy_provided() -> None:
    """The ``partial_failure`` scenario has a busy block — it must render."""
    inp = SCENARIOS["partial_failure"].build()
    assert inp.calendar_free_busy, "scenario should provide a busy block"
    out = schedule(inp)
    html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    assert '<rect class="busy-block"' in html


def test_unscheduled_section_empty_message_on_full_success() -> None:
    """On full success the unscheduled section should show its 'none' message."""
    inp = SCENARIOS["success"].build()
    out = schedule(inp)
    assert not out.unscheduled_tasks
    html = render_schedule_html(scheduler_input=inp, scheduler_output=out)
    assert "every validated task was placed" in html


def test_cli_list_scenarios_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """`--list-scenarios` prints the scenario directory and returns 0."""
    rc = main(["--list-scenarios"])
    assert rc == 0
    out = capsys.readouterr().out
    for name in SCENARIOS:
        assert name in out


def test_cli_writes_file_for_each_scenario(tmp_path: Path) -> None:
    """`--out` writes a real HTML file containing an SVG for every scenario."""
    for name in sorted(SCENARIOS):
        target = tmp_path / f"{name}.html"
        rc = main(["--scenario", name, "--out", str(target)])
        assert rc == 0
        assert target.exists(), f"file not created for {name}"
        content = target.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "<!doctype html>" in content


def test_cli_creates_missing_parent_directories(tmp_path: Path) -> None:
    """``--out path/to/missing/dir/file.html`` must mkdir the parents."""
    target = tmp_path / "nested" / "deep" / "out.html"
    rc = main(["--scenario", "success", "--out", str(target)])
    assert rc == 0
    assert target.exists()


def test_cli_unknown_scenario_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """argparse's ``choices=`` produces a non-zero exit for unknown scenarios."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--scenario", "does_not_exist"])
    assert exc_info.value.code != 0
