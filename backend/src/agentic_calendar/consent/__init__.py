"""Consent region (Phase 6a; ADR-0007).

Owns the deterministic opt-in surface for cross-user data use: the
consent-record grant/revoke lifecycle, the append-only data-access audit log,
the consent gate that every pooled-training / pooled-serving /
cohort-retrieval read must pass, and the view/export/delete data controls.

Determinism boundary: consent state is a typed state machine
(``contracts/consent_record.py``); the gate's allow/deny decision and every
audit entry carry typed reason codes. No consent state is ever derived from
LLM prose, chat history, or free text.

Allowed dependencies (enforced by ``backend/.importlinter``): ``common``,
``contracts``. This region is a leaf — it imports no other region; the
composition root (operator CLIs, Phase 6b training wiring) passes user-scoped
data sources in from outside the region set.
"""

from __future__ import annotations

from .audit_store import (
    AuditEntryAlreadyExistsError,
    DataAccessAuditStore,
    DataAccessAuditStoreError,
    InMemoryDataAccessAuditStore,
)
from .data_controls import (
    DuplicateSourceNameError,
    UserDataSource,
    collect_user_data,
    delete_user_data,
)
from .gate import GATED_PURPOSE_TO_SCOPE, ConsentDecision, ConsentGate
from .store import (
    ConsentAlreadyGrantedError,
    ConsentRecordAlreadyExistsError,
    ConsentRecordNotFoundError,
    ConsentStore,
    ConsentStoreError,
    IllegalConsentTransitionError,
    InMemoryConsentStore,
    NonGrantedConsentInsertError,
)

__all__ = [
    "GATED_PURPOSE_TO_SCOPE",
    "AuditEntryAlreadyExistsError",
    "ConsentAlreadyGrantedError",
    "ConsentDecision",
    "ConsentGate",
    "ConsentRecordAlreadyExistsError",
    "ConsentRecordNotFoundError",
    "ConsentStore",
    "ConsentStoreError",
    "DataAccessAuditStore",
    "DataAccessAuditStoreError",
    "DuplicateSourceNameError",
    "IllegalConsentTransitionError",
    "InMemoryConsentStore",
    "InMemoryDataAccessAuditStore",
    "NonGrantedConsentInsertError",
    "UserDataSource",
    "collect_user_data",
    "delete_user_data",
]
