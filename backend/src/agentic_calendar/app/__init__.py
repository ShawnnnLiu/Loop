"""Application composition root (Phase 9b).

This package sits OUTSIDE the region set, like ``tools/``: it may import any
region and wire them together, but no region may import it. It owns nothing a
region owns — routing stays in ``supervisor/``, validation in ``validation/``,
scheduling in ``scheduler/``, calendar writes in ``calendar_writer/``. The
composition root only sequences those deterministic services, persists the
supervisor state between operator commands, and preserves every typed
``reason_code`` on the way through.

No invariant is relaxed here for ergonomics: calendar writes still require an
``approval_event_id`` and pass the ``approved_payload_hash`` recheck; LLM
output still passes boundary validation before any deterministic consumer
sees it; repair loops stay bounded at two attempts.
"""
