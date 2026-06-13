"""``threshold_change_log`` contract.

Canonical spec: ``docs/specs/threshold-change-log.schema.md``.

:class:`ThresholdChange` is the append-only audit record for one modification
of one deterministic tuning knob. Axiom 07 ("Threshold Change Log") requires
every threshold modification to be recorded with its prior value, new value,
justification, and motivating dataset; this contract generalizes that journal
from the drift thresholds to every scalar field of the registered config
dataclasses.

The section vocabulary is owned by the tuning registry in ``app/tuning.py``;
this contract validates shape only. Entries are audit facts, never control
plane: ``justification`` is bounded prose for humans, and no runtime routing
decision reads this record.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator

#: Shape-only vocabulary check; the registry owns which names actually exist.
_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"


class ThresholdChange(BaseModel):
    """Append-only audit record for one tuning-value change (axiom 07)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: str = Field(min_length=1)
    config_section: str = Field(pattern=_IDENTIFIER_PATTERN)
    threshold_field: str = Field(pattern=_IDENTIFIER_PATTERN)
    # Strict number types: booleans are not tunable numbers and must not
    # validate (``True == 1`` would otherwise slip through lax coercion).
    prior_value: StrictInt | StrictFloat
    new_value: StrictInt | StrictFloat
    effective_at: datetime
    justification: str = Field(min_length=1, max_length=500)
    dataset_reference: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _effective_at_aware(self) -> ThresholdChange:
        if self.effective_at.tzinfo is None:
            raise ValueError("effective_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _value_actually_changed(self) -> ThresholdChange:
        # Numeric comparison on purpose: 1 and 1.0 are the same value, and a
        # no-op entry would fake an audit trail (spec "Invalid Examples").
        if self.new_value == self.prior_value:
            raise ValueError("new_value must differ from prior_value")
        return self
