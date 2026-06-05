"""Cache region errors."""

from __future__ import annotations

from agentic_calendar.common.errors import AgenticCalendarError


class CacheError(AgenticCalendarError):
    """Base for cache-region errors."""
