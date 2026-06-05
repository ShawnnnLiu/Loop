"""Source-claim coverage checks for a syllabus (axiom 08).

Validates that a ``SyllabusUnits`` proposal cites evidence honestly:

* every ``source_claim_id`` a module references resolves to a known claim;
* no referenced claim is expired (axiom 08: "expired claims must not drive new
  syllabus generation unless refreshed");
* a company-specific module cites at least one claim when the strategy
  constraint requires it.

Pure function returning a list of ``Violation`` records; never mutates inputs
(axiom 04). Imports ``contracts/`` only — it reads claims through the registry
and calls :meth:`SourceClaim.is_expired`, so it does not depend on the
``source_claims`` kernel (regions stay independent).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation


def check_source_claims(
    syllabus: SyllabusUnits,
    *,
    claim_registry: Mapping[str, SourceClaim],
    now: datetime,
    must_reference_claims_for_company_specific_modules: bool,
) -> list[Violation]:
    """Return source-claim violations for ``syllabus`` against ``claim_registry``."""
    violations: list[Violation] = []

    for module in syllabus.modules:
        for claim_id in module.source_claim_ids:
            claim = claim_registry.get(claim_id)
            if claim is None:
                violations.append(
                    make_violation(
                        ViolationType.ORPHAN_SOURCE_CLAIM,
                        module_id=module.module_id,
                        claim_id=claim_id,
                    )
                )
            elif claim.is_expired(now):
                violations.append(
                    make_violation(
                        ViolationType.EXPIRED_SOURCE_CLAIM,
                        module_id=module.module_id,
                        claim_id=claim_id,
                        expires_at=claim.expires_at.isoformat(),
                    )
                )

        if (
            must_reference_claims_for_company_specific_modules
            and module.company_specific
            and not module.source_claim_ids
        ):
            violations.append(
                make_violation(
                    ViolationType.COMPANY_MODULE_MISSING_CLAIM,
                    module_id=module.module_id,
                )
            )

    return violations
