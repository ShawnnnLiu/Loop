"""Append-only knowledge-map overlay store (narrative-pathways KT-B).

An account's knowledge map is the generated :class:`KnowledgeMap`(s) of its
selected pathway(s) **plus** the append-only overlay of the six ``frozen``
record types in ``contracts/knowledge_map_overlay.py`` (spec:
``knowledge-map-overlay.schema.md``). This store is that overlay: onboarding /
evidence flows append :class:`MasteryGrant`s and :class:`NodeAddition`s; the user
appends personal :class:`CustomGroup`s, :class:`CustomNode`s, :class:`NodeNote`s
and :class:`MasterySetPoint`s.

Append-only by construction, mirroring the task-disposition store: there is no
update or single-record delete surface, only ``append`` and per-user reads, so
"subtract" has no representation (the ``06-…`` add-only rule enforced
structurally). ``delete_for_user`` exists solely for the ADR-0007 data-delete
control, exactly like ``identity`` / ``consent`` / ``disposition``.

Reads are per-user and per-record-type, in insertion order - the deterministic
fold order the ``map_state`` kernel (KT-B) relies on. Per-account id uniqueness
and the personal-content count caps are the add-node / CRUD API's concern
(KT-C, ``CUSTOM_CONTENT_LIMIT_EXCEEDED``), not the store's.

Leaf kernel: depends only on ``common`` and ``contracts``.
"""

from __future__ import annotations

import threading
from typing import Protocol, TypeVar, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomGroup,
    CustomNode,
    MasteryGrant,
    MasterySetPoint,
    NodeAddition,
    NodeNote,
)

#: Any of the six overlay record types (all ``frozen``, all carry ``user_id``).
OverlayRecord = (
    NodeAddition | CustomGroup | CustomNode | NodeNote | MasteryGrant | MasterySetPoint
)

_R = TypeVar("_R", bound=OverlayRecord)


class KnowledgeOverlayStoreError(AgenticCalendarError):
    """Base for knowledge-overlay-store errors."""


@runtime_checkable
class KnowledgeOverlayStore(Protocol):
    """Append / read / delete surface for a knowledge-map overlay."""

    def append(self, record: OverlayRecord) -> None: ...

    def node_additions_for_user(self, user_id: str) -> list[NodeAddition]: ...

    def custom_groups_for_user(self, user_id: str) -> list[CustomGroup]: ...

    def custom_nodes_for_user(self, user_id: str) -> list[CustomNode]: ...

    def notes_for_user(self, user_id: str) -> list[NodeNote]: ...

    def mastery_grants_for_user(self, user_id: str) -> list[MasteryGrant]: ...

    def setpoints_for_user(self, user_id: str) -> list[MasterySetPoint]: ...

    def delete_for_user(self, user_id: str) -> int: ...


class InMemoryKnowledgeOverlayStore:
    """Default store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._records: list[OverlayRecord] = []
        self._lock = threading.RLock()

    def append(self, record: OverlayRecord) -> None:
        with self._lock:
            self._records.append(record)

    def _typed(self, user_id: str, cls: type[_R]) -> list[_R]:
        with self._lock:
            return [
                r
                for r in self._records
                if r.user_id == user_id and isinstance(r, cls)
            ]

    def node_additions_for_user(self, user_id: str) -> list[NodeAddition]:
        return self._typed(user_id, NodeAddition)

    def custom_groups_for_user(self, user_id: str) -> list[CustomGroup]:
        return self._typed(user_id, CustomGroup)

    def custom_nodes_for_user(self, user_id: str) -> list[CustomNode]:
        return self._typed(user_id, CustomNode)

    def notes_for_user(self, user_id: str) -> list[NodeNote]:
        return self._typed(user_id, NodeNote)

    def mastery_grants_for_user(self, user_id: str) -> list[MasteryGrant]:
        return self._typed(user_id, MasteryGrant)

    def setpoints_for_user(self, user_id: str) -> list[MasterySetPoint]:
        return self._typed(user_id, MasterySetPoint)

    def delete_for_user(self, user_id: str) -> int:
        """Remove every record for ``user_id`` (ADR-0007 data-delete control)."""
        with self._lock:
            keep = [r for r in self._records if r.user_id != user_id]
            removed = len(self._records) - len(keep)
            self._records = keep
            return removed
