# Golden Test Cases

The system must include deterministic test scenarios that exercise the core invariants. These tests are the ground truth for "does the system still work?" and must be runnable on every commit.

Each test must define expected output, typed `reason_code`, privacy behavior, and next action where applicable.

## Required Scenarios

1. **Limited weekly capacity** — User has only 3 free hours per week. Expect Scheduler to either fit a reduced plan or emit `INSUFFICIENT_WEEKLY_CAPACITY` with repair options.
2. **No weekday availability** — User has no weekday availability. Expect Scheduler to schedule on weekends only, respecting `allow_weekends` and deep work windows.
3. **Cycle in task graph** — Task graph contains a cycle. Expect validator to fail with `CYCLE_DETECTED` and repair payload listing the cycle members.
4. **Orphan dependency** — Task depends on a nonexistent task. Expect validator to fail with `ORPHAN_DEPENDENCY` and the invalid `task_id`.
5. **Task too long, unsplittable** — Task is longer than `max_session_length_min` and `splittable: false`. Expect `TASK_TOO_LONG_UNSPLITTABLE` and policy action "ask user".
6. **Calendar full except short gaps** — Calendar is full except for short gaps. Expect `NO_VALID_CONTIGUOUS_BLOCK` and `suggested_repair: "split_task"` in the debug payload.
7. **Topic avoidance** — User repeatedly misses only DP tasks. Expect drift classifier to emit `topic_avoidance` with at least 3 missed tasks in the evidence.
8. **User-edited generated event** — User manually edits a generated calendar event. Expect mapping `user_modified_bool: true`, no overwrite on next write, and policy code `USER_MODIFIED_EVENT`.
9. **Calendar write partial failure** — Calendar write partially fails. Expect Calendar Write Manager to detect missing events by `run_id`, retry only missing tasks, or rollback by `run_id`.
10. **Malformed Planner JSON** — Planner produces malformed JSON. Expect schema validator to fail with `VALIDATION_FAILED`, route to repair (attempt 1), then to `error_requires_user` after 2 failures.
11. **Dropped high-priority module** — Planner drops a high-priority module. Expect coverage validator to fail with `module_coverage_missing` and force a repair attempt.
12. **Timeline infeasibility** — Scheduler cannot fit tasks within timeline. Expect `INSUFFICIENT_WEEKLY_CAPACITY` and deterministic repair options including `extend_timeline` and `reduce_scope`.
13. **Plan rejection and scope reduction** — User rejects generated plan and requests scope reduction. Expect a new plan version, deterministic diff, and unchanged active plan until approval.
14. **Approved write but verification fails** — User approves draft, but write verification fails. Expect `CALENDAR_WRITE_UNVERIFIED`, retry verification, and rollback if verification still fails.
15. **Capacity but no contiguous block** — User has enough total time but no valid contiguous block. Expect `NO_VALID_CONTIGUOUS_BLOCK` with `largest_available_block_min` populated and `split_task` suggested.

## Accountability and Sponsor Scenarios

16. **Private nudge at missed-task threshold** — User misses 2 tasks in 7 days. Expect `MISSED_TASK_THRESHOLD_REACHED`, a private in-app nudge only, and no sponsor notification.
17. **Sponsor summary when enabled and threshold hit** — User misses 4 tasks in 7 days with sponsor reporting enabled. Expect `SPONSOR_REPORT_PENDING`, a draft `summary_only` sponsor report, and `requires_user_approval_before_send: true`.
18. **Sponsor disabled, no report generated** — User misses 4 tasks in 7 days but sponsor reporting is disabled. Expect `ACCOUNTABILITY_CONTRACT_INACTIVE` for the sponsor path, no sponsor report draft, and a private user nudge only.
19. **Sponsor report privacy filter** — Sponsor report draft attempts to include raw calendar titles or essay drafts. Expect `SPONSOR_VISIBILITY_VIOLATION`, the draft is blocked, and an engineering-review log entry is written.
20. **Sponsor visibility downgrade** — User changes `sponsor_visibility_level` from `task_completion` to `summary_only`. Expect the next generated report to include only summary fields; task-level details must be absent.
21. **Weekly check-in due** — Weekly check-in is due but not completed. Expect `CHECKIN_DUE`, a check-in prompt, and no recovery plan draft until the user responds or `CHECKIN_MISSED` fires.
22. **Behind-schedule recovery plan** — User is 25% behind schedule. Expect `BEHIND_SCHEDULE_THRESHOLD_REACHED`, a recovery plan draft, and that the active plan is not mutated in place.
23. **Accountability mismatch** — User repeatedly falls behind but rejects sponsor reporting. Expect drift type `accountability_mismatch`, policy action `revise_accountability_contract`, and no sponsor notification.
24. **Accountability contract disabled** — User disables the accountability contract. Expect `ACCOUNTABILITY_CONTRACT_INACTIVE`, no further sponsor reports or nudges, and that the active plan is unaffected.
25. **Disallowed LLM sponsor wording** — LLM-generated sponsor summary attempts to include disallowed private details. Expect the privacy filter to reject the draft with `SPONSOR_VISIBILITY_VIOLATION` before send.

## Additional Required Scenarios

The deterministic invariants in `axioms/16-reliability-patterns.md` also require:

- Approval missing → no calendar write executes; `USER_APPROVAL_REQUIRED` is emitted.
- Repair limit exceeded → `REPAIR_LIMIT_EXCEEDED` and route to `error_requires_user`.
- Source claim expired → `SOURCE_CLAIM_EXPIRED` and refresh or downgrade confidence.
- Profile major change → `PROFILE_MAJOR_CHANGE` invalidates syllabus and plan.
- Capacity change → `CAPACITY_CHANGE` invalidates schedule but keeps syllabus and tasks.

## Test Structure

For each scenario, tests must assert:

- The exact typed `reason_code`.
- The structure of the debug or repair payload.
- The Supervisor's next state.
- That no calendar write occurs without `approval_event_id`.
- That validation does not mutate the artifact under test.

## Related Docs

- `axioms/04-validation-layer.md`
- `axioms/05-scheduler-policy.md`
- `axioms/06-calendar-safety.md`
- `axioms/07-telemetry-and-drift.md`
- `axioms/12-edge-case-policy-engine.md`
- `axioms/16-reliability-patterns.md`
- `axioms/21-accountability-layer.md`
- `specs/motivation-profile.schema.md`
