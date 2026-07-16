.PHONY: help install sync test test-fast lint typecheck format boundaries schemas schema-check eval-gate retrieval-eval visualize check clean

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
	@echo "  retrieval-eval  grade the labeled retrieval query set against the pinned corpus snapshot (corpus/corpus.db, committed)"
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
# fixture_improved. The v2 pairs grade EVERY committed v2 recording —
# baseline (2026-07-05, pre-D1 prompts), fewshot (post-D1), and voice
# (post-D2, the SHIPPED prompts; newest = shipped) — all with the same
# floors. Floors are the MEASURED values (schema validity 1.0000 on all
# three); repair recovery was n/a (no case needed repair), so its floor is
# vacuous on these recordings and arms on the first recording that
# exercises repair. Grading a committed recording is deterministic —
# floors equal to measured always pass until a new recording lands.
# The v3 pair (resume_intake, RI-E) grades the FixtureResumeIntake
# recording — validity there includes the groundedness/vocabulary
# invariants, so the gate also guards the eval wiring itself.
eval-gate:
	uv run python -m agentic_calendar.tools.run_llm_eval --strict \
		--eval-set evalsets/eval_set_v1.json \
		--recording evalsets/recordings/fixture_improved.json
	uv run python -m agentic_calendar.tools.run_llm_eval --strict \
		--eval-set evalsets/eval_set_v2.json \
		--recording evalsets/recordings/baseline_2026_07_05.json \
		--min-schema-validity-rate 1.0 --min-repair-recovery-rate 1.0
	uv run python -m agentic_calendar.tools.run_llm_eval --strict \
		--eval-set evalsets/eval_set_v2.json \
		--recording evalsets/recordings/fewshot_2026_07_05.json \
		--min-schema-validity-rate 1.0 --min-repair-recovery-rate 1.0
	uv run python -m agentic_calendar.tools.run_llm_eval --strict \
		--eval-set evalsets/eval_set_v2.json \
		--recording evalsets/recordings/voice_2026_07_05.json \
		--min-schema-validity-rate 1.0 --min-repair-recovery-rate 1.0
	uv run python -m agentic_calendar.tools.run_llm_eval --strict \
		--eval-set evalsets/eval_set_v3.json \
		--recording evalsets/recordings/fixture_resume_intake.json \
		--min-schema-validity-rate 1.0 --min-repair-recovery-rate 1.0
	uv run python -m agentic_calendar.tools.run_llm_eval --strict \
		--eval-set evalsets/eval_set_v4.json \
		--recording evalsets/recordings/grounding_2026_07_06.json \
		--min-schema-validity-rate 1.0 --min-repair-recovery-rate 1.0 \
		--min-citation-coverage 0.6444

# The v4 pair grades the grounded/ungrounded twins (grounding-RAG G-H).
# citation-coverage floor seeded at the measured grounded-arm value
# (2026-07-06 capture: coverage 0.6444, utilization 0.8667, zero unknown
# citations) — a heuristic prior like every seeded floor.

# Retrieval eval gate (grounding-RAG G-D). Deterministic like eval-gate —
# queries + labels + snapshot pin are all versioned. Since 2026-07-14 the
# corpus database IS committed (owner decision: corpus/corpus.db holds only
# public-web text — axiom 08 — and re-fetching does not reproduce the bytes
# behind the pinned snapshot, so reproducibility of these floors won over
# keeping page text out of the repo; see the writeup's post-publication
# updates). This target therefore runs anywhere the repo is checked out.
# It is not wired into CI or `check` yet — a follow-up decision.
# Floors are the values MEASURED on the v2 labeled run (75 cases, 2026-07-15,
# snapshot snap_0217291f46e331b9 — the fetch-checkpoint expansion to 30+ docs
# per track, curated to the latest document per source URL): heuristic priors
# until more labels accumulate. Floor history: v1 3-track 0.9181/0.8523/0.8380;
# v2 six-track (snap_26c44499e582a96a, 55 docs) 0.8978/0.8500/0.8327; this run
# (188 docs) 0.7644/0.7144/0.6910. The drop is honest, not a regression bug:
# 3.4x the corpus means more ranking competition, and the v2 labels predate
# the expansion — every zero-recall case spot-checked retrieves NEW on-topic
# documents the labels cannot credit (e.g. the drift query now finds the two
# dedicated drift articles instead of the labeled rules-of-ml page). A v3
# label pass crediting the expanded corpus is the natural follow-up. Floors
# equal to measured always pass until the labels, corpus, chunking, or
# ranking change.
retrieval-eval:
	uv run python -m agentic_calendar.tools.run_retrieval_eval --strict \
		--queries evalsets/retrieval_queries_v2.json \
		--db corpus/corpus.db \
		--snapshot snap_0217291f46e331b9 \
		--k 5 \
		--min-recall 0.7644 --min-mrr 0.7144 --min-ndcg 0.6910

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
