"""Tie ``prompt_version`` to the prompt bytes (axiom 22 measurement hygiene).

``prompt_version`` is a hand-maintained constant with no structural link to the
prompt text it labels. An edit without a version bump would silently mislabel
every call-log row and eval comparison. This test pins a SHA-256 of each system
prompt next to its version string: changing a prompt fails here until the hash
AND the version are updated together.

To update after an intentional prompt change:

    uv run python -c "import hashlib; \
from agentic_calendar.llm_nodes import anthropic_adapter as aa; \
print(hashlib.sha256(aa._PLANNER_SYSTEM.encode()).hexdigest())"

then bump the node's ``prompt_version`` (new date suffix) and replace the
pinned pair below.
"""

from __future__ import annotations

import hashlib

import pytest

from agentic_calendar.llm_nodes import anthropic_adapter as adapter

#: (prompt constant name, config, pinned prompt_version, pinned SHA-256).
_PINNED: list[tuple[str, object, str, str]] = [
    (
        "_STRATEGIST_SYSTEM",
        adapter.STRATEGIST_CONFIG,
        "strategist-v3-2026-07-05",
        "60fa04c32e9f33929f921fdc3c576ed72097b55a9c303d4309d9893175d4c093",
    ),
    (
        "_PLANNER_SYSTEM",
        adapter.PLANNER_CONFIG,
        "planner-v3-2026-07-05",
        "c90d36545131255891d1498644ef793c932684572c9d0dacc4350d18603e324c",
    ),
    (
        "_REFLECTION_SYSTEM",
        adapter.REFLECTION_CONFIG,
        "reflection-v2-2026-06-23",
        "fa73d22e31882293c3a47f5d3f6c0e2cd3b3e0b7da5c9e602c2417e7ab1202c8",
    ),
    (
        "_EXPLANATION_SYSTEM",
        adapter.EXPLANATION_CONFIG,
        "explanation-v2-2026-06-23",
        "9d558b3a714614315a799b2992282f49888266cfb895a51a7198356198c7ae01",
    ),
]


@pytest.mark.parametrize(
    ("constant_name", "config", "pinned_version", "pinned_sha256"),
    _PINNED,
    ids=[name.strip("_").lower() for name, _, _, _ in _PINNED],
)
def test_prompt_version_matches_prompt_bytes(
    constant_name: str,
    config: adapter.AdapterConfig,
    pinned_version: str,
    pinned_sha256: str,
) -> None:
    prompt_text = getattr(adapter, constant_name)
    actual_sha256 = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    assert config.prompt_version == pinned_version, (
        f"{constant_name}: prompt_version changed without updating the pinned "
        f"pair in this test — keep version and hash in lockstep"
    )
    assert actual_sha256 == pinned_sha256, (
        f"{constant_name}: prompt bytes changed. Bump the node's prompt_version "
        f"(new date suffix) and update the pinned hash here in the same commit; "
        f"new hash: {actual_sha256}"
    )
