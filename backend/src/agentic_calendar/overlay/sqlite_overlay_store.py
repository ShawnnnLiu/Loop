"""SQLite knowledge-map overlay store (restart-survival twin).

Persistent twin of
:class:`~agentic_calendar.overlay.overlay_store.InMemoryKnowledgeOverlayStore`:
same :class:`~agentic_calendar.overlay.overlay_store.KnowledgeOverlayStore`
protocol, same append-only invariant. One row per overlay record holds the
canonical Pydantic JSON dump plus the ``user_id`` and a ``record_type``
discriminator; reads rebuild the frozen model with ``model_validate_json`` so a
round trip is contract-validated, never trusted. Insertion order (``rowid``) is
the fold order the ``map_state`` kernel relies on.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomGroup,
    CustomNode,
    MasteryGrant,
    MasterySetPoint,
    NodeAddition,
    NodeNote,
)

from .overlay_store import OverlayRecord

_SCHEMA_COMPONENT = "overlay.knowledge_overlay_records"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS knowledge_overlay_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        record_type TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_knowledge_overlay_user_type
        ON knowledge_overlay_records (user_id, record_type)
    """,
)

# Discriminator <-> contract class. The string is stored, never the class name,
# so a rename of the Python class cannot silently reshape persisted rows.
_TYPE_BY_CLASS: dict[type[OverlayRecord], str] = {
    NodeAddition: "node_addition",
    CustomGroup: "custom_group",
    CustomNode: "custom_node",
    NodeNote: "node_note",
    MasteryGrant: "mastery_grant",
    MasterySetPoint: "mastery_setpoint",
}


class SqliteKnowledgeOverlayStore:
    """Persistent overlay store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, record: OverlayRecord) -> None:
        record_type = _TYPE_BY_CLASS[type(record)]
        with self._db.transaction() as cur:
            cur.execute(
                "INSERT INTO knowledge_overlay_records (user_id, record_type, payload)"
                " VALUES (?, ?, ?)",
                (record.user_id, record_type, record.model_dump_json()),
            )

    def _load(self, user_id: str, cls: type[OverlayRecord]) -> list[OverlayRecord]:
        record_type = _TYPE_BY_CLASS[cls]
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM knowledge_overlay_records"
                " WHERE user_id = ? AND record_type = ? ORDER BY id",
                (user_id, record_type),
            ).fetchall()
        return [cls.model_validate_json(row[0]) for row in rows]

    def node_additions_for_user(self, user_id: str) -> list[NodeAddition]:
        return [r for r in self._load(user_id, NodeAddition) if isinstance(r, NodeAddition)]

    def custom_groups_for_user(self, user_id: str) -> list[CustomGroup]:
        return [r for r in self._load(user_id, CustomGroup) if isinstance(r, CustomGroup)]

    def custom_nodes_for_user(self, user_id: str) -> list[CustomNode]:
        return [r for r in self._load(user_id, CustomNode) if isinstance(r, CustomNode)]

    def notes_for_user(self, user_id: str) -> list[NodeNote]:
        return [r for r in self._load(user_id, NodeNote) if isinstance(r, NodeNote)]

    def mastery_grants_for_user(self, user_id: str) -> list[MasteryGrant]:
        return [r for r in self._load(user_id, MasteryGrant) if isinstance(r, MasteryGrant)]

    def setpoints_for_user(self, user_id: str) -> list[MasterySetPoint]:
        return [
            r for r in self._load(user_id, MasterySetPoint) if isinstance(r, MasterySetPoint)
        ]

    def delete_for_user(self, user_id: str) -> int:
        """Remove every record for ``user_id`` (ADR-0007 data-delete control)."""
        with self._db.transaction() as cur:
            cur.execute(
                "DELETE FROM knowledge_overlay_records WHERE user_id = ?", (user_id,)
            )
            return cur.rowcount
