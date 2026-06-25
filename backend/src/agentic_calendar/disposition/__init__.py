"""Disposition region — completion / drop memory.

Append-only memory of what a user completed, skipped, or dropped
(``docs/specs/task-disposition.schema.md``; ADR-0008). Two deterministic
consumers read it from the composition root: the scheduler projection
(``SchedulerInput.completed_task_ids``) and the completion-relative
drag-to-adjust advisory check.

Allowed dependencies (enforced by ``backend/.importlinter``): ``common``,
``contracts``. This region is a leaf — it imports no other region; the
composition root (``app/``) wires the projection, and the data-control CLI
deletes it, both from outside the region set.
"""

from __future__ import annotations

from .disposition_store import (
    InMemoryTaskDispositionStore,
    TaskDispositionAlreadyExistsError,
    TaskDispositionStore,
    TaskDispositionStoreError,
)

__all__ = [
    "InMemoryTaskDispositionStore",
    "TaskDispositionAlreadyExistsError",
    "TaskDispositionStore",
    "TaskDispositionStoreError",
]
