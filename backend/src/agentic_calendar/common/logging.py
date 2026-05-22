"""Structured logging helpers.

Every public function that touches a plan should attach the correlation
identifiers (``run_id``, ``plan_version``, ``task_id``) to its log records so
that a failure can be reconstructed end-to-end. We use the standard
``logging.LoggerAdapter`` to inject these without forcing every call site to
repeat them.

Phase 1 keeps the implementation deliberately small: a function to obtain a
correlated adapter and a context manager to temporarily bind correlation
fields. We do **not** wire structured JSON output yet — that lands when the
HTTP layer arrives in Phase 2.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from typing import Any

_LOGGER_NAME_PREFIX = "agentic_calendar"


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under ``agentic_calendar.<name>``.

    Pass ``__name__`` from the call site, e.g.::

        log = get_logger(__name__)
    """
    if not name:
        raise ValueError("logger name must be non-empty")
    if name.startswith(_LOGGER_NAME_PREFIX):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_NAME_PREFIX}.{name}")


class CorrelatedAdapter(logging.LoggerAdapter):  # type: ignore[type-arg]
    """``LoggerAdapter`` that prefixes every record with correlation fields.

    Bound fields are appended to the message as ``key=value`` pairs so that
    the human-readable text already carries the context. When the JSON
    formatter lands in Phase 2 it can pull from ``record.extra`` instead.
    """

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        extra: Mapping[str, Any] = self.extra or {}
        if not extra:
            return msg, kwargs
        suffix = " ".join(f"{k}={v}" for k, v in sorted(extra.items()) if v is not None)
        if suffix:
            msg = f"{msg} [{suffix}]"
        existing = kwargs.get("extra") or {}
        kwargs["extra"] = {**extra, **existing}
        return msg, kwargs


def correlated(
    logger: logging.Logger,
    *,
    run_id: str | None = None,
    plan_version: str | None = None,
    task_id: str | None = None,
    **extra: Any,
) -> CorrelatedAdapter:
    """Return a ``LoggerAdapter`` with the supplied correlation IDs bound."""
    bound: dict[str, Any] = {
        "run_id": run_id,
        "plan_version": plan_version,
        "task_id": task_id,
        **extra,
    }
    bound = {k: v for k, v in bound.items() if v is not None}
    return CorrelatedAdapter(logger, bound)


@contextmanager
def log_context(
    logger: logging.Logger,
    *,
    run_id: str | None = None,
    plan_version: str | None = None,
    task_id: str | None = None,
    **extra: Any,
) -> Iterator[CorrelatedAdapter]:
    """Yield a correlated adapter for use inside a ``with`` block."""
    adapter = correlated(
        logger,
        run_id=run_id,
        plan_version=plan_version,
        task_id=task_id,
        **extra,
    )
    yield adapter
