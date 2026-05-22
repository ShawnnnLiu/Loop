"""Run ``import-linter`` as a pytest boundary check.

This makes the architectural boundaries enforced by ``backend/.importlinter``
part of every ``pytest`` run, not just CI. Marked ``@pytest.mark.boundary``
so it can be selected/excluded explicitly when speed matters.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
"""``backend/`` directory containing ``.importlinter``."""


@pytest.mark.boundary
def test_import_linter_contracts_all_pass() -> None:
    result = subprocess.run(
        ["uv", "run", "lint-imports", "--config", ".importlinter"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "import-linter contracts broken:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.boundary
def test_no_llm_sdk_imports_outside_llm_nodes_or_tools() -> None:
    """Spot-check via filesystem grep — fast supplement to import-linter.

    If a future commit imports an LLM SDK from a non-allowed package, this
    test fails before ``lint-imports`` even runs.
    """
    src = BACKEND_ROOT / "src" / "agentic_calendar"
    llm_sdks = ("openai", "anthropic", "cohere", "mistralai")
    offenders: list[str] = []
    for path in src.rglob("*.py"):
        rel = path.relative_to(src).as_posix()
        if rel.startswith(("llm_nodes/", "tools/")):
            continue
        text = path.read_text(encoding="utf-8")
        for sdk in llm_sdks:
            if f"import {sdk}" in text or f"from {sdk}" in text:
                offenders.append(f"{rel}: imports {sdk}")
    assert offenders == [], (
        "Found LLM-SDK imports outside llm_nodes/tools:\n  " + "\n  ".join(offenders)
    )
