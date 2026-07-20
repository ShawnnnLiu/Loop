"""Shared duplicate-detection and case-folding helpers for contract validators.

Centralizes two policies that several contracts - and, from NP-B, the
``narrative/`` kernel - must apply *identically*:

* exact-match duplicate detection with a deterministic, sorted report
  (:func:`find_duplicates`);
* the single canonical case-insensitive comparison form for free-text
  vocabulary - theme tags, a slot's ``required_themes_any``, and the
  ``(title, organization)`` identity of an experience item
  (:func:`casefold_key`).

Before this module the same ``list.count()`` dedup and an ad-hoc ``.lower()``
were copy-pasted across ``pathway_template``, ``pathway_selection``,
``strategy_constraints``, and ``user_profile``, with the case-folding policy
decided independently at each call site. Routing every case-insensitive
comparison through :func:`casefold_key` makes that policy one line of code the
kernel can import, so a theme tagged ``"Applied-ML"`` and a slot requiring
``"applied-ml"`` are guaranteed to join the same way everywhere.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

# str for id / theme / enum-value lists; tuple for the (title, organization)
# identity of an experience item. Both are hashable and sortable, so the
# duplicate report is deterministic.
_Comparable = TypeVar("_Comparable", str, tuple[str, str])


def find_duplicates(values: Iterable[_Comparable]) -> list[_Comparable]:
    """Return the sorted distinct values that appear more than once.

    Exact-match: normalize case-insensitive fields through :func:`casefold_key`
    *before* calling this. The sorted result gives validators a stable,
    reproducible duplicate list for their error messages.
    """
    seen: set[_Comparable] = set()
    duplicates: set[_Comparable] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return sorted(duplicates)


def casefold_key(value: str) -> str:
    """The canonical case-insensitive comparison form for a free-text token.

    Every case-insensitive comparison over user vocabulary - ``skills``
    uniqueness, theme-tag uniqueness, ``required_themes_any`` uniqueness,
    experience-item identity in slot overrides, and the ``narrative/`` kernel's
    theme join (NP-B) - must normalize through this one function so they can
    never diverge.
    """
    return value.casefold()
