"""Subprocess smoke tests for the registered console scripts.

The in-process ``main(argv)`` tests in ``test_export_schemas.py`` /
``test_visualize.py`` cannot detect broken ``[project.scripts]`` wiring (a
typo'd entry-point string would pass every in-process test and fail only at
install time). These spawn the real entry points once each.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]

_SCRIPTS = ("agentic-calendar-export-schemas", "agentic-calendar-visualize")


@pytest.mark.subprocess
@pytest.mark.parametrize("script", _SCRIPTS)
def test_console_script_entry_point_is_wired(script: str) -> None:
    result = subprocess.run(
        ["uv", "run", script, "--help"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"{script} --help failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "usage" in result.stdout.lower()
