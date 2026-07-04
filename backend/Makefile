.PHONY: help install sync test test-fast lint typecheck format boundaries schemas schema-check eval-gate visualize check clean

help:
	@echo "Targets:"
	@echo "  install     install dev dependencies into backend/.venv via uv"
	@echo "  sync        alias for install"
	@echo "  test        run the full pytest suite"
	@echo "  test-fast   run pytest excluding slow tests (golden scenarios, subprocess boundary checks)"
	@echo "  lint        ruff check"
	@echo "  format      ruff format (writes changes)"
	@echo "  typecheck   mypy --strict on src/"
	@echo "  boundaries  import-linter contracts (LLM SDK isolation, layering)"
	@echo "  schemas     regenerate /schemas/*.schema.json from Pydantic contracts"
	@echo "  schema-check verify committed /schemas match the contracts (no write)"
	@echo "  eval-gate   strict-grade committed eval recordings (offline; amended axiom 22)"
	@echo "  visualize   render the 'success' scheduler scenario to ../schedule.html"
	@echo "  check       lint + typecheck + schema-check + test (boundaries run inside test)"
	@echo "  clean       remove caches and build artifacts"

install sync:
	uv sync --extra dev

test:
	uv run pytest

test-fast:
	uv run pytest -m "not golden and not boundary and not subprocess"

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src

boundaries:
	uv run lint-imports --config .importlinter

schemas:
	uv run python -m agentic_calendar.tools.export_schemas --out ../schemas

schema-check:
	uv run python -m agentic_calendar.tools.export_schemas --out ../schemas --check

# Grades COMMITTED recordings only — deterministic and offline, so it may
# gate merges (amended axiom 22; live-call evals still never run in CI).
# The fixture_baseline recording deliberately contains a failing case (it
# proves the harness measures failures), so the strict pair here is
# fixture_improved. When a real v2 baseline is captured, add its pair with
# floors seeded from that baseline, e.g.:
#   uv run python -m agentic_calendar.tools.run_llm_eval --strict \
#     --eval-set evalsets/eval_set_v2.json \
#     --recording evalsets/recordings/baseline_YYYY_MM_DD.json \
#     --min-schema-validity-rate <seeded> --min-repair-recovery-rate <seeded>
eval-gate:
	uv run python -m agentic_calendar.tools.run_llm_eval --strict \
		--eval-set evalsets/eval_set_v1.json \
		--recording evalsets/recordings/fixture_improved.json

visualize:
	uv run agentic-calendar-visualize --scenario success --out ../schedule.html
	@echo "open ../schedule.html in your browser"

# `test` already runs the boundary-marked tests (the same lint-imports
# binary plus the LLM-SDK grep), so chaining `boundaries` here would run
# import-linter twice per CI job. `make boundaries` stays as the focused
# local target.
check: lint typecheck schema-check test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
