"""Local web surface over the Phase 9 composition root (Frontend Stage 0, F0a).

This subpackage lives inside ``app/`` — the composition root — for the same
reason ``cycle.py`` does: it may wire any region together, but no region may
import it. It owns FastAPI routing and (later) server-rendered pages; the
deterministic core is untouched and every axiom-06 calendar-safety invariant
still holds because every request goes through :class:`CycleService`, never
around it.

The Google OAuth SDK is *not* imported here (the boundary grep forbids
``google`` imports outside ``llm_nodes``/``tools``). The web layer passes and
receives plain token JSON and opaque ``service`` objects across the
``tools/`` seam — exactly as the operator CLI does today.
"""

from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]
