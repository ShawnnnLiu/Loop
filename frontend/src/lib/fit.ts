// Pure formatters that turn the backend's structured validation violations into
// specific, human-readable recovery lines. React-free so they unit-test without
// a DOM runner (same split as lib/approval.ts). Deterministic display only — the
// typed reason_code stays the contract; this just makes the numbers concrete so
// a user-fit failure card isn't a guessing game ("needs ~140h, you budgeted ~96h").

import type { Violation } from '../api/types'

// Mirror of contracts/violation_types.py::ViolationType values we can explain.
const WEEKLY_LOAD = 'weekly_load_exceeds_capacity'
const MAX_SESSION = 'duration_exceeds_user_max_session'
const FAR_FROM_PREFERRED = 'duration_far_from_preferred'
const COGNITIVE_LOAD = 'cognitive_load_out_of_range'

function num(details: Record<string, unknown>, key: string): number | null {
  const v = details[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

/** Plan-scale minutes -> "~Xh". One decimal under 10h, whole hours above. */
function hours(min: number): string {
  const h = min / 60
  const rounded = h >= 10 ? Math.round(h) : Math.round(h * 10) / 10
  return `${rounded}h`
}

/** One human line per violation we know how to explain; unknown types return
 *  null (the generic recovery hint still shows for them). */
export function formatViolation(v: Violation): string | null {
  const d = v.details
  switch (v.type) {
    case WEEKLY_LOAD: {
      const total = num(d, 'total_plan_min')
      const cap = num(d, 'capacity_min')
      if (total === null || cap === null) return null
      const weeks = num(d, 'timeline_weeks')
      const wh = num(d, 'weekly_hours')
      const budget = weeks !== null && wh !== null ? ` (${weeks} weeks × ${wh}h/week)` : ''
      return (
        `The plan needs about ${hours(total)} but your budget is about ${hours(cap)}${budget}. ` +
        `Raise weekly hours, extend the timeline, or narrow the goal.`
      )
    }
    case MAX_SESSION: {
      const dur = num(d, 'duration_min')
      const max = num(d, 'max_session_length_min')
      if (dur === null || max === null) return null
      return `A ${dur}-min block is longer than your ${max}-min max session. Raise your max session length.`
    }
    case FAR_FROM_PREFERRED: {
      const dur = num(d, 'duration_min')
      const pref = num(d, 'preferred_session_length_min')
      if (dur === null || pref === null) return null
      return `A ${dur}-min block is well under your preferred ${pref}-min session. Lower your preferred session length.`
    }
    case COGNITIVE_LOAD: {
      const load = num(d, 'cognitive_load')
      return load === null ? null : `A task's cognitive load (${load}) is outside the allowed 1–5 range.`
    }
    default:
      return null
  }
}

/** De-duplicated, order-preserving specific lines for a failure's violations. */
export function formatViolations(violations: Violation[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const v of violations) {
    const line = formatViolation(v)
    if (line && !seen.has(line)) {
      seen.add(line)
      out.push(line)
    }
  }
  return out
}
