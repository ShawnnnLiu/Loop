"""Tuning loader — the only supported path for changing a tuning value.

Axiom 07 ("Threshold Change Log") forbids silent threshold changes; this
module generalizes that rule from the drift thresholds to every deterministic
tuning knob that lives in a registered config dataclass. The flow is:

1. ``load_tuning_file`` parses ``tuning.toml`` (stdlib ``tomllib``).
2. ``apply_tuning`` validates every override against :data:`TUNABLE_SECTIONS`,
   journals each *effective* change to the append-only
   :class:`~agentic_calendar.app.threshold_log.ThresholdChangeLogStore`
   (``docs/specs/threshold-change-log.schema.md``), and returns the
   :class:`EffectiveTuning` the composition root serves from.

Invariants:

- Only scalar (``int`` / ``float``) dataclass fields are tunable; structured
  fields (e.g. ``calibration.quality_weights``) are rejected with a typed
  :class:`TuningError`, never silently ignored.
- Re-applying the same file appends nothing (idempotent re-load): an entry is
  journaled only when the override differs from the current effective value
  (the default, or the last journaled ``new_value`` for that field).
- Overrides require a top-level ``justification`` and ``dataset_reference``
  — axiom 07 makes both mandatory parts of the audit record.
- All values remain heuristic priors until calibration (axiom 07 "MVP
  Disclosure"); this mechanism journals the priors' evolution, it does not
  bless them as tuned.

Removing an override from the file (or running without a file) reverts
serving to the code default **and journals that reversion**: ``apply_tuning``
appends an entry with ``prior_value`` = the replayed journal value and
``new_value`` = the default for every journaled override the file no longer
carries. The file's top-level prose is reused when present; otherwise
:data:`REVERSION_JUSTIFICATION` and :data:`REVERSION_DATASET_REFERENCE` (or
:data:`ABSENT_DATASET_REFERENCE` when no file was supplied at all) fill the
audit record. Re-applying the same file or absence appends nothing — the
replayed value already equals the default.
"""

from __future__ import annotations

import dataclasses
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_type_hints

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.threshold_change_log import ThresholdChange
from agentic_calendar.drift.thresholds import DEFAULT_DRIFT_THRESHOLDS, DriftThresholds
from agentic_calendar.duration_estimation.pooled import (
    DEFAULT_POOLED_SERVING_CONFIG,
    DEFAULT_POOLED_TRAINING_CONFIG,
    PooledServingConfig,
    PooledTrainingConfig,
)
from agentic_calendar.duration_estimation.power_user import (
    DEFAULT_ELIGIBILITY_CONFIG,
    DEFAULT_REFINEMENT_CONFIG,
    EligibilityConfig,
    RefinementConfig,
)
from agentic_calendar.source_claims.curation import (
    DEFAULT_CLAIM_CURATION_CONFIG,
    ClaimCurationConfig,
)
from agentic_calendar.telemetry.calibration import (
    DEFAULT_CALIBRATION_CONFIG,
    CalibrationConfig,
)

from .threshold_log import ThresholdChangeLogStore

#: Section name → (config dataclass, default instance). This registry owns the
#: ``config_section`` vocabulary; the contract validates shape only (spec
#: "Scope"). Section names must match :class:`EffectiveTuning` field names.
TUNABLE_SECTIONS: dict[str, tuple[type[Any], Any]] = {
    "drift_thresholds": (DriftThresholds, DEFAULT_DRIFT_THRESHOLDS),
    "calibration": (CalibrationConfig, DEFAULT_CALIBRATION_CONFIG),
    "pooled_training": (PooledTrainingConfig, DEFAULT_POOLED_TRAINING_CONFIG),
    "pooled_serving": (PooledServingConfig, DEFAULT_POOLED_SERVING_CONFIG),
    "power_user_eligibility": (EligibilityConfig, DEFAULT_ELIGIBILITY_CONFIG),
    "per_user_refinement": (RefinementConfig, DEFAULT_REFINEMENT_CONFIG),
    "claim_curation": (ClaimCurationConfig, DEFAULT_CLAIM_CURATION_CONFIG),
}

#: Top-level file keys that are not sections.
_PROSE_KEYS = frozenset({"justification", "dataset_reference"})

#: Audit prose for journaled reversions when the tuning file carries no
#: top-level prose of its own (a file with no active overrides does not
#: require any). Both stay within the contract's length bounds.
REVERSION_JUSTIFICATION = "tuning override removed; reverted to code default"
REVERSION_DATASET_REFERENCE = "tuning.toml"

#: ``dataset_reference`` for reversions journaled on ``apply_tuning(parsed=None)``
#: — there is no file to point at.
ABSENT_DATASET_REFERENCE = "tuning file absent"


class TuningError(AgenticCalendarError):
    """A tuning file failed validation against the registry.

    Raised for: unknown section, unknown field, non-scalar field override
    attempt, wrong value type, or overrides without justification /
    dataset_reference. Always names the offender — a rejected file must be
    fixable from the error message alone.
    """


@dataclass(frozen=True)
class EffectiveTuning:
    """The effective config instance per section (defaults when no file)."""

    drift_thresholds: DriftThresholds
    calibration: CalibrationConfig
    pooled_training: PooledTrainingConfig
    pooled_serving: PooledServingConfig
    power_user_eligibility: EligibilityConfig
    per_user_refinement: RefinementConfig
    claim_curation: ClaimCurationConfig


@dataclass(frozen=True)
class ParsedOverrides:
    """A validated tuning file: per-section scalar overrides plus prose."""

    overrides: Mapping[str, Mapping[str, int | float]]
    justification: str | None
    dataset_reference: str | None


def load_tuning_file(path: str | Path) -> dict[str, Any]:
    """Parse a ``tuning.toml`` file (stdlib ``tomllib``); no validation yet."""
    with Path(path).open("rb") as f:
        return tomllib.load(f)


def scalar_fields(config_type: type[Any]) -> dict[str, type[int] | type[float]]:
    """The tunable (``int`` / ``float``) fields of one config dataclass.

    ``get_type_hints`` resolves the string annotations the config modules use
    (``from __future__ import annotations``); anything that is not exactly
    ``int`` or ``float`` — mappings, enums, optionals — is not tunable. Public
    because the read-only ``show_thresholds`` CLI renders this surface.
    """
    hints = get_type_hints(config_type)
    return {
        f.name: hints[f.name]
        for f in dataclasses.fields(config_type)
        if hints[f.name] in (int, float)
    }


def _validate_value(
    section: str, field_name: str, value: object, expected: type[int] | type[float]
) -> int | float:
    """Type-check one override value; floats accept ints, nothing accepts bool."""
    label = f"{section}.{field_name}"
    if isinstance(value, bool):
        raise TuningError(f"field {label} expects {expected.__name__}, got bool")
    if expected is int:
        if not isinstance(value, int):
            raise TuningError(f"field {label} expects int, got {type(value).__name__}")
        return value
    if not isinstance(value, int | float):
        raise TuningError(f"field {label} expects float, got {type(value).__name__}")
    return float(value)


def extract_overrides(parsed: Mapping[str, Any]) -> ParsedOverrides:
    """Validate a parsed tuning file against the registry. Read-only.

    Shared by :func:`apply_tuning` (which then journals) and the read-only
    ``show_thresholds`` preview (which must not). ``justification`` and
    ``dataset_reference`` are required iff at least one override is present —
    even an override that turns out to be a no-op was an operator decision
    that needs its prose.
    """
    overrides: dict[str, dict[str, int | float]] = {}
    for key, table in parsed.items():
        if key in _PROSE_KEYS:
            if not isinstance(table, str):
                raise TuningError(f"top-level {key!r} must be a string")
            continue
        if key not in TUNABLE_SECTIONS:
            raise TuningError(
                f"unknown tuning section {key!r}; known sections: "
                f"{', '.join(TUNABLE_SECTIONS)}"
            )
        if not isinstance(table, Mapping):
            raise TuningError(f"tuning section {key!r} must be a table of field overrides")
        config_type, _default = TUNABLE_SECTIONS[key]
        scalars = scalar_fields(config_type)
        section_overrides: dict[str, int | float] = {}
        for field_name, value in table.items():
            if not any(f.name == field_name for f in dataclasses.fields(config_type)):
                raise TuningError(
                    f"unknown field {field_name!r} in tuning section {key!r}"
                )
            if field_name not in scalars:
                raise TuningError(
                    f"field {key}.{field_name} is not a scalar tunable; only "
                    "int/float fields can be overridden through tuning.toml"
                )
            section_overrides[field_name] = _validate_value(
                key, field_name, value, scalars[field_name]
            )
        if section_overrides:
            overrides[key] = section_overrides

    justification = parsed.get("justification")
    dataset_reference = parsed.get("dataset_reference")
    if overrides:
        if justification is None:
            raise TuningError(
                "tuning overrides require a top-level justification (axiom 07)"
            )
        if dataset_reference is None:
            raise TuningError(
                "tuning overrides require a top-level dataset_reference (axiom 07)"
            )
    return ParsedOverrides(
        overrides=overrides,
        justification=justification,
        dataset_reference=dataset_reference,
    )


def replay_effective(store: ThresholdChangeLogStore) -> dict[str, dict[str, int | float]]:
    """Section → field → latest journaled value, replayed deterministically.

    Insertion order is the journal's ordering contract, so the last entry per
    ``(config_section, threshold_field)`` wins — the same rule
    :func:`apply_tuning` uses to compute ``prior_value``.
    """
    effective: dict[str, dict[str, int | float]] = {}
    for change in store.list_all():
        effective.setdefault(change.config_section, {})[change.threshold_field] = (
            change.new_value
        )
    return effective


def _required_prose(value: str | None, name: str) -> str:
    if value is None:  # unreachable after extract_overrides; typed narrowing
        raise TuningError(f"tuning overrides require a top-level {name} (axiom 07)")
    return value


def _append_reversions(
    *,
    replayed: Mapping[str, Mapping[str, int | float]],
    file_overrides: Mapping[str, Mapping[str, int | float]],
    store: ThresholdChangeLogStore,
    clock: Clock,
    id_generator: IdGenerator,
    justification: str,
    dataset_reference: str,
) -> None:
    """Journal a reversion for every journaled override no longer in force.

    Reverting to the default is a threshold change too (axiom 07): for every
    ``(section, field)`` whose replayed journal value differs from the
    dataclass default and which the file does not override, append one entry
    with ``prior_value`` = the replayed value and ``new_value`` = the
    default. Idempotent: once journaled, the replayed value equals the
    default and the next apply appends nothing.
    """
    for section, (_config_type, default) in TUNABLE_SECTIONS.items():
        for field_name, replayed_value in replayed.get(section, {}).items():
            if field_name in file_overrides.get(section, {}):
                continue
            default_value = getattr(default, field_name)
            if replayed_value == default_value:
                continue
            store.append(
                ThresholdChange(
                    change_id=id_generator.new_id("thrchg"),
                    config_section=section,
                    threshold_field=field_name,
                    prior_value=replayed_value,
                    new_value=default_value,
                    effective_at=clock.now(),
                    justification=justification,
                    dataset_reference=dataset_reference,
                )
            )


def apply_tuning(
    *,
    parsed: Mapping[str, Any] | None,
    store: ThresholdChangeLogStore,
    clock: Clock,
    id_generator: IdGenerator,
) -> EffectiveTuning:
    """Validate, journal, and return the effective tuning.

    For each override the *current* effective value is the default unless the
    journal already has entries for that field, in which case the last
    entry's ``new_value``. An override equal to the current value appends
    nothing (idempotent re-load); a differing one appends exactly one
    :class:`ThresholdChange` — there is no other write path, which is what
    makes "no silent threshold changes" (axiom 07) structural.

    The returned :class:`EffectiveTuning` always reflects the file's values:
    after this call the replayed journal and the file agree on every
    overridden field — and on every *removed* one. A journaled override the
    file no longer carries journals a reversion entry (``prior_value`` = the
    replayed value, ``new_value`` = the default), with the file's prose when
    present or :data:`REVERSION_JUSTIFICATION` /
    :data:`REVERSION_DATASET_REFERENCE` otherwise — reverting is never a
    silent change.

    ``parsed=None`` always returns all defaults; if the replayed journal
    still shows a non-default value, the same reversion entries are appended
    (``dataset_reference`` = :data:`ABSENT_DATASET_REFERENCE`). A fresh
    journal appends nothing.
    """
    if parsed is None:
        _append_reversions(
            replayed=replay_effective(store),
            file_overrides={},
            store=store,
            clock=clock,
            id_generator=id_generator,
            justification=REVERSION_JUSTIFICATION,
            dataset_reference=ABSENT_DATASET_REFERENCE,
        )
        return EffectiveTuning(
            **{name: default for name, (_, default) in TUNABLE_SECTIONS.items()}
        )
    tuning_file = extract_overrides(parsed)
    replayed = replay_effective(store)
    effective_configs: dict[str, Any] = {}
    for section, (_config_type, default) in TUNABLE_SECTIONS.items():
        section_overrides = tuning_file.overrides.get(section, {})
        for field_name, value in section_overrides.items():
            current = replayed.get(section, {}).get(
                field_name, getattr(default, field_name)
            )
            if value == current:
                continue
            store.append(
                ThresholdChange(
                    change_id=id_generator.new_id("thrchg"),
                    config_section=section,
                    threshold_field=field_name,
                    prior_value=current,
                    new_value=value,
                    effective_at=clock.now(),
                    justification=_required_prose(
                        tuning_file.justification, "justification"
                    ),
                    dataset_reference=_required_prose(
                        tuning_file.dataset_reference, "dataset_reference"
                    ),
                )
            )
        effective_configs[section] = (
            dataclasses.replace(default, **dict(section_overrides))
            if section_overrides
            else default
        )
    _append_reversions(
        replayed=replayed,
        file_overrides=tuning_file.overrides,
        store=store,
        clock=clock,
        id_generator=id_generator,
        justification=(
            tuning_file.justification
            if tuning_file.justification is not None
            else REVERSION_JUSTIFICATION
        ),
        dataset_reference=(
            tuning_file.dataset_reference
            if tuning_file.dataset_reference is not None
            else REVERSION_DATASET_REFERENCE
        ),
    )
    return EffectiveTuning(**effective_configs)
