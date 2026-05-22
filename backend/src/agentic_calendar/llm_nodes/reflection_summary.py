"""Reflection-summary node — Phase 1 stub.

The reflection-summary node will (in later phases) generate a short
human-readable progress summary from telemetry. Phase 1 keeps a typed stub
so callers can already wire to the protocol; the stub raises
``NotImplementedError`` rather than returning a fake string because Phase 1
has nothing concrete to summarise yet.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReflectionSummary(BaseModel):
    """A short, structured summary returned by the reflection node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1)


class StubReflectionSummary:
    """Raises ``NotImplementedError`` until Phase 4 wires telemetry in."""

    def run(self, *, run_id: str, **_: object) -> ReflectionSummary:
        del run_id
        raise NotImplementedError(
            "ReflectionSummary is implemented in Phase 4 alongside the telemetry layer."
        )
