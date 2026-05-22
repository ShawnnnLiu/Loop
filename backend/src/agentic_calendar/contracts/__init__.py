"""Pydantic data contracts.

One module per canonical schema in ``docs/specs/``. Treat these models as the
boundary between LLM proposals and deterministic services. Update the spec
first, then the model, then producer/consumer code (see
``docs/axioms/03-data-contracts.md``).

``contracts`` is a leaf package: it depends only on ``common``. The
``import-linter`` ``contracts-is-leaf`` rule enforces this.
"""
