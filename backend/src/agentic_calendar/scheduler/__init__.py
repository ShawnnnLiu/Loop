"""Pure greedy Scheduler — Phase 1 MVP (``docs/axioms/05-scheduler-policy.md``).

The Scheduler creates draft schedules only. It does not call calendar APIs and
must not bypass validation. Failures emit typed ``reason_code`` with debug
payloads matching ``docs/specs/scheduler-output.schema.md``.

Phase 3 may swap the greedy core for OR-Tools CP-SAT without changing this
package's external contract.
"""

from .greedy import schedule
from .inputs import FreeBusyInterval, SchedulerInput
from .policy import DeepWorkWindowPolicy, SchedulingPolicy, policy_from_user_profile

__all__ = [
    "DeepWorkWindowPolicy",
    "FreeBusyInterval",
    "SchedulerInput",
    "SchedulingPolicy",
    "policy_from_user_profile",
    "schedule",
]
