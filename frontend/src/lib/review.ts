// Pure logic for the Week (schedule-review) screen: from the latest run's
// state, decide whether its draft is still an editable awaiting-approval draft
// or an already-written / active schedule that must render read-only — plus the
// honest banner copy for each read-only case. React-free and unit-tested, the
// same split as lib/approval.ts, so the screen stays a thin view over server
// truth (the server, not the client, owns which transitions are legal).

import type { StatusResult } from '../api/types'

export type ReviewMode = 'editable' | 'written' | 'writing' | 'failed' | 'replan'

/** Drag-to-adjust and approval are valid ONLY while the run awaits approval —
 *  the server enforces the same guard (adjust/approve both require
 *  AWAITING_USER_APPROVAL and 409 otherwise), so every other state must render
 *  read-only. A verified write activates the plan (ACTIVE_PLAN and its
 *  downstream drift / terminal states); the two calendar_write_* progress
 *  states are transient mid-write; a failed write leaves the plan unactivated.
 *  A run parked in replan_required is the flagship feedback loop surfacing —
 *  it must NEVER collapse into "your week is scheduled". A missing/blank state
 *  (no run yet) has no editable draft. */
export function reviewMode(status: StatusResult | null): ReviewMode {
  switch (status?.state) {
    case 'awaiting_user_approval':
      return 'editable'
    case 'calendar_write_approved':
    case 'calendar_write_in_progress':
      return 'writing'
    case 'calendar_write_failed':
      return 'failed'
    case 'replan_required':
      return 'replan'
    default:
      return 'written'
  }
}

/** Plain-language cause for a replan, from the typed reason_code the drift
 *  classifier stamped on the run. Deterministic map — the LLM reflection prose
 *  is a separate, advisory attachment (surfaced in a later increment). */
export function replanReason(reasonCode: string | null | undefined): string {
  switch (reasonCode) {
    case 'DRIFT_DURATION_UNDERESTIMATE':
      return 'tasks have been taking longer than planned'
    case 'DRIFT_DURATION_OVERESTIMATE':
      return 'tasks have been finishing faster than planned'
    case 'DRIFT_CAPACITY_MISMATCH':
      return 'your available time and the plan no longer line up'
    case 'DRIFT_EXTERNAL_CONFLICT':
      return 'changes on your calendar conflict with planned blocks'
    case 'DRIFT_DEPENDENCY_BLOCKED':
      return 'a stuck task is holding up the work that depends on it'
    case 'DRIFT_CALENDAR_FRAGMENTATION':
      return 'your remaining free time is too fragmented for the longer blocks'
    case 'ACCOUNTABILITY_MISMATCH':
      return 'recent check-ins suggest the current pace isn’t working'
    case 'SPONSOR_PRESSURE_MISMATCH':
      return 'your accountability setup needs adjusting'
    case 'USER_RECOMMITMENT_REQUIRED':
      return 'you chose to adjust your commitment'
    default:
      return 'your progress has drifted from the plan'
  }
}

/** The three deterministic recovery modes the user can pick when their
 *  motivation profile says ask_each_time. Values mirror the backend's
 *  RecoveryAction enum; descriptions are plain-language, not clinical. */
export interface RecoveryOption {
  mode: 'reschedule' | 'scope_reduction' | 'extend_timeline'
  title: string
  description: string
}

export const RECOVERY_OPTIONS: RecoveryOption[] = [
  {
    mode: 'reschedule',
    title: 'Reschedule',
    description: 'Keep everything, move the remaining work to times that still fit.',
  },
  {
    mode: 'scope_reduction',
    title: 'Reduce the load',
    description: 'Trim lower-priority work so the plan fits the time you actually have.',
  },
  {
    mode: 'extend_timeline',
    title: 'Extend the timeline',
    description: 'Keep the full plan and spread it over more weeks.',
  },
]

/** The "needs attention" chip for Today (and anywhere else the user lives):
 *  a parked run should be visible without visiting the Week screen. Returns
 *  null for every healthy/transient state. */
export function attentionChip(
  state: string | null | undefined,
): { label: string; to: string } | null {
  switch (state) {
    case 'replan_required':
      return { label: 'Your plan needs an update', to: '/review' }
    case 'calendar_write_failed':
      return { label: 'A calendar write needs attention', to: '/approve' }
    case 'error_requires_user':
      return { label: 'Your last plan run stopped — review and restart', to: '/plan' }
    default:
      return null
  }
}

export interface ReviewBanner {
  title: string
  sub: string
}

/** Banner copy for the read-only modes. 'failed' is the careful one: the
 *  engine does not auto-roll-back, so it must NOT claim the blocks are on the
 *  calendar and must say the plan wasn't activated (same honesty as
 *  writeFailureMessage in lib/approval.ts). 'replan' names the drift cause
 *  from the run's typed reason_code — pass the status for that. The 'editable'
 *  banner is bespoke — it carries the drag instructions and the approval CTA —
 *  so the screen renders that one directly. */
export function reviewBanner(mode: ReviewMode, status?: StatusResult | null): ReviewBanner {
  switch (mode) {
    case 'written':
      return {
        title: 'Your week is scheduled',
        sub: 'These blocks are written to your Google Calendar and confirmed. Track them and check them off in Today.',
      }
    case 'writing':
      return {
        title: 'Writing your week…',
        sub: 'Loop is writing these blocks to your calendar and verifying each one. This page is read-only until that finishes.',
      }
    case 'failed':
      return {
        title: 'The last write didn’t fully verify',
        sub: 'These blocks aren’t confirmed on your calendar and your plan wasn’t activated. Open the approval screen to retry the missing events or remove what was written.',
      }
    case 'replan':
      return {
        title: 'Your plan needs an update',
        sub:
          `Loop noticed ${replanReason(status?.reason_code)}. ` +
          (status?.recovery_mode_pending_user_choice
            ? 'Choose how to adjust below — a new draft goes through the full review and approval, nothing changes silently.'
            : 'Build the updated plan below — it goes through the full review and approval, nothing changes silently.'),
      }
    case 'editable':
      return { title: 'Review your proposed week', sub: '' }
  }
}
