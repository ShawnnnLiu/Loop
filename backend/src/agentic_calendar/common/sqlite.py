"""Shared SQLite kernel (Phase 9a).

stdlib-only (``sqlite3``) so every region's ``Sqlite*Store`` can depend on it
without adding a dependency or breaking the import-linter contracts
(``common`` is the one package every region may import).

One :class:`SqliteDatabase` instance wraps one database file and is shared by
every store the composition root wires. Thread-safety mirrors the in-memory
stores: a single ``RLock`` serializes every transaction, so two threads can
never observe a torn write — the same contract the in-memory twins advertise.

Schema management is deterministic: each store registers its tables with
``ensure_schema`` using idempotent ``CREATE TABLE IF NOT EXISTS`` statements
and a declared integer version recorded in the ``schema_version`` table. A
version mismatch raises — there is no silent migration path in the
single-user MVP; a future migration framework is the production story.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from agentic_calendar.common.errors import AgenticCalendarError


class SqliteKernelError(AgenticCalendarError):
    """Base for SQLite-kernel errors that callers may catch."""


class SchemaVersionMismatchError(SqliteKernelError):
    """The on-disk schema version differs from what this code expects.

    Raised instead of migrating: the MVP has no migration framework, so a
    mismatch must fail loudly rather than guess at a transformation.
    """

    def __init__(self, component: str, *, on_disk: int, expected: int) -> None:
        self.component = component
        self.on_disk = on_disk
        self.expected = expected
        super().__init__(
            f"schema component {component!r} is at version {on_disk} on disk "
            f"but this code expects version {expected}"
        )


class SqliteDatabase:
    """One SQLite database file, shared by every ``Sqlite*Store``.

    Transactions do not nest: a store method must do all of its SQL inside a
    single ``transaction()`` (or ``read()``) block and never call another
    method that opens its own transaction while one is active.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._lock = threading.RLock()
        # ``isolation_level=None`` puts sqlite3 in autocommit mode so that
        # transaction boundaries are the explicit BEGIN/COMMIT/ROLLBACK in
        # ``transaction()`` — never the driver's implicit ones.
        self._conn = sqlite3.connect(
            self._path, check_same_thread=False, isolation_level=None
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def path(self) -> str:
        return self._path

    def ensure_schema(
        self, component: str, *, version: int, statements: Sequence[str]
    ) -> None:
        """Idempotently create ``component``'s tables and pin their version.

        ``statements`` must each be a single idempotent DDL statement
        (``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS``);
        they run inside one transaction together with the version check.
        """
        with self.transaction() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                " component TEXT PRIMARY KEY,"
                " version INTEGER NOT NULL)"
            )
            row = cur.execute(
                "SELECT version FROM schema_version WHERE component = ?",
                (component,),
            ).fetchone()
            if row is not None and row[0] != version:
                raise SchemaVersionMismatchError(
                    component, on_disk=row[0], expected=version
                )
            for statement in statements:
                cur.execute(statement)
            if row is None:
                cur.execute(
                    "INSERT INTO schema_version (component, version) VALUES (?, ?)",
                    (component, version),
                )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """One serialized read-write transaction.

        Commits on normal exit; rolls back on any exception — so a store can
        enforce an invariant by writing first, checking, and raising, exactly
        like the in-memory stores' save-then-rollback pattern.
        """
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE")
                yield cur
            except BaseException:
                self._conn.rollback()
                raise
            else:
                self._conn.commit()
            finally:
                cur.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Cursor]:
        """One serialized read-only cursor (autocommit; takes no write lock)."""
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def close(self) -> None:
        """Close the connection. Reopen by constructing a new instance."""
        with self._lock:
            self._conn.close()
