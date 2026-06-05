"""Telemetry region (Phase 4).

Privacy-first capture of how scheduled tasks actually executed, plus the
deterministic functions that consume it: duration calibration and metrics. The
drift classifier lives in the sibling ``drift`` region and reads
:class:`~agentic_calendar.contracts.telemetry.TelemetryEvent` objects, not this
package, so the two regions stay independent (``.importlinter``).

This region is a leaf: it depends only on ``common`` and ``contracts``.
"""
