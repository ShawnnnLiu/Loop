"""Agentic Calendar — deterministic career-preparation orchestration engine.

Read ``AGENTS.md`` and ``docs/axioms/`` before making substantive changes.

Module layout (Phase 1):

* ``common``         — shared kernel: clock, IDs, errors, structured logging.
* ``contracts``      — Pydantic models, one per ``docs/specs/`` schema. Leaf.
* ``supervisor``     — pure routing function + state enum + transition table.
* ``prerequisites``  — deterministic prerequisite computation (axiom 11).
* ``validation``     — five-category validation layer (axiom 04).
* ``scheduler``      — pure greedy MVP scheduler (axiom 05).
* ``planning``       — immutable plan versions + generation history (axiom 15).
* ``llm_nodes``      — the only package allowed to import LLM SDKs (axiom 01).
* ``tools``          — operator CLIs (e.g. schema export).

Architectural boundaries are enforced by ``backend/.importlinter`` and the
``tests/boundaries/`` suite. A fault in one region must not be able to reach
into another; cross-region data flow is mediated by ``contracts``.
"""

__version__ = "0.1.0"
