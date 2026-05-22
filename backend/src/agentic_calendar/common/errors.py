"""Base exception hierarchy.

Every region defines its own region-local subclass of ``AgenticCalendarError``
in its own ``errors.py`` module. The cardinal rule is: **no region lets a raw
``Exception`` cross its public surface**. Region-internal exceptions are
caught at the boundary and translated to a typed ``ReasonCode``-bearing
result. This keeps a fault contained to its region.

Exceptions defined here exist only as the common base so that callers may
catch the package's exceptions without importing every region's module.
"""

from __future__ import annotations


class AgenticCalendarError(Exception):
    """Root of every domain exception in this package.

    Subclass in each region (e.g. ``ValidationError`` inside
    ``validation/errors.py``). Never raise this base directly; always raise a
    region-specific subclass so the catch site has typed handling.
    """


class ContractError(AgenticCalendarError):
    """A Pydantic contract violation that escaped local handling.

    Producers should construct ``ValidationResult`` objects with structured
    violations rather than raising. This exception exists for the rare case
    where invalid data appears at a code boundary that has no contract-level
    response (e.g. internal invariants, ``tools/`` CLIs).
    """


class InvariantError(AgenticCalendarError):
    """A core invariant was violated (see ``axioms/16-reliability-patterns.md``).

    Raised by the (future) invariant checker that runs after every node. In
    Phase 1 it exists so that any code that detects "this should never happen"
    has a typed exception to raise rather than a bare ``AssertionError``.
    """
