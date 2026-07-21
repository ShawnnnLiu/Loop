"""``overlay/`` — the append-only knowledge-map overlay store (KT-B).

The per-account overlay behind the knowledge map: onboarding / evidence flows
append :class:`MasteryGrant`s and :class:`NodeAddition`s (pathway content); the
user appends personal :class:`CustomGroup`s, :class:`CustomNode`s,
:class:`NodeNote`s and :class:`MasterySetPoint`s. Append-only by construction
(the ``06-…`` add-only rule enforced structurally), mirroring the
task-disposition store's in-memory / SQLite split so the persistent twin can
swap in for restart survival.

Leaf kernel: depends only on ``common`` and ``contracts``. The composition root
(``app/``) wires it; the map API (KT-C) and the ``map_state`` kernel consume its
records as plain data - the kernel never imports this region.
"""

from .overlay_store import (
    InMemoryKnowledgeOverlayStore,
    KnowledgeOverlayStore,
    KnowledgeOverlayStoreError,
    OverlayRecord,
)
from .sqlite_overlay_store import SqliteKnowledgeOverlayStore

__all__ = [
    "InMemoryKnowledgeOverlayStore",
    "KnowledgeOverlayStore",
    "KnowledgeOverlayStoreError",
    "OverlayRecord",
    "SqliteKnowledgeOverlayStore",
]
