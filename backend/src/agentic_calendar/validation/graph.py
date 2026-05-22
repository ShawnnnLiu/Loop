"""Graph-integrity checks (axiom 04).

Detects:

* duplicate ``task_id`` values;
* orphan dependencies (references to non-existent tasks);
* self-dependencies;
* cycles (including the cycle membership for repair payloads).

The Pydantic contract already rejects two of these (duplicate IDs,
self-dependencies) at parse time, but this module is the single place where
we report them as ``ViolationType`` records for the validation layer; it also
catches them when the upstream parse was bypassed (e.g. when re-validating a
plan stored as a dict).
"""

from __future__ import annotations

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation


def check_task_graph(plan: TaskPlan) -> list[Violation]:
    """Return graph-integrity violations, if any.

    Order of checks matters for repair clarity: duplicates → orphans →
    self-deps → cycles. We report all violations rather than short-circuiting
    so the LLM can repair multiple in a single attempt.
    """
    violations: list[Violation] = []
    violations.extend(_duplicates(plan))
    valid_ids = {t.task_id for t in plan.tasks}
    violations.extend(_orphans(plan, valid_ids))
    violations.extend(_self_deps(plan))
    violations.extend(_cycles(plan, valid_ids))
    return violations


def _duplicates(plan: TaskPlan) -> list[Violation]:
    seen: dict[str, int] = {}
    violations: list[Violation] = []
    for t in plan.tasks:
        seen[t.task_id] = seen.get(t.task_id, 0) + 1
    for tid, count in seen.items():
        if count > 1:
            violations.append(
                make_violation(
                    ViolationType.DUPLICATE_TASK_ID,
                    task_id=tid,
                    count=count,
                )
            )
    return violations


def _orphans(plan: TaskPlan, valid_ids: set[str]) -> list[Violation]:
    violations: list[Violation] = []
    for t in plan.tasks:
        for dep in t.dependencies:
            if dep not in valid_ids:
                violations.append(
                    make_violation(
                        ViolationType.ORPHAN_DEPENDENCY,
                        task_id=t.task_id,
                        invalid_dependency=dep,
                    )
                )
    return violations


def _self_deps(plan: TaskPlan) -> list[Violation]:
    violations: list[Violation] = []
    for t in plan.tasks:
        if t.task_id in t.dependencies:
            violations.append(
                make_violation(
                    ViolationType.SELF_DEPENDENCY,
                    task_id=t.task_id,
                )
            )
    return violations


def _cycles(plan: TaskPlan, valid_ids: set[str]) -> list[Violation]:
    """Detect cycles via DFS; report each distinct cycle once.

    Edges to non-existent tasks are skipped here (they are already reported
    as orphans). Self-edges are skipped (reported as ``self_dependency``).
    """
    graph: dict[str, list[str]] = {
        t.task_id: [d for d in t.dependencies if d in valid_ids and d != t.task_id]
        for t in plan.tasks
    }
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(graph, WHITE)
    parent: dict[str, str | None] = dict.fromkeys(graph, None)
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        for nbr in graph.get(node, []):
            if color.get(nbr, WHITE) == WHITE:
                parent[nbr] = node
                dfs(nbr)
            elif color[nbr] == GRAY:
                # Found a back edge node -> nbr; cycle is nbr ... node -> nbr.
                cycle: list[str] = [nbr]
                cur: str | None = node
                while cur is not None and cur != nbr:
                    cycle.append(cur)
                    cur = parent.get(cur)
                cycle.reverse()
                if cycle and cycle[0] != cycle[-1]:
                    cycle.append(nbr)
                cycles.append(cycle)
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            dfs(node)

    if not cycles:
        return []

    deduped = _dedupe_cycles(cycles)
    return [
        make_violation(
            ViolationType.CYCLE_DETECTED,
            members=cycle,
        )
        for cycle in deduped
    ]


def _dedupe_cycles(cycles: list[list[str]]) -> list[list[str]]:
    """Treat cycles as equal up to rotation; keep canonical (min-rotated) form."""
    seen: set[tuple[str, ...]] = set()
    out: list[list[str]] = []
    for cycle in cycles:
        canon = _canonicalize_cycle(cycle)
        if canon not in seen:
            seen.add(canon)
            out.append(list(canon))
    return out


def _canonicalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Return the rotation that starts at the lexicographically smallest node."""
    nodes = cycle[:-1] if cycle and cycle[0] == cycle[-1] else cycle
    if not nodes:
        return tuple(cycle)
    smallest = min(range(len(nodes)), key=lambda i: nodes[i])
    rotated = nodes[smallest:] + nodes[:smallest]
    return tuple([*rotated, rotated[0]])
