import { describe, expect, it } from 'vitest'

import type { PlanDiffView, StatusResult } from '../api/types'
import {
  RECOVERY_OPTIONS,
  attentionChip,
  planDiffLine,
  replanReason,
  reviewBanner,
  reviewMode,
  setupDeepLink,
} from './review'

function status(
  state: StatusResult['state'],
  over: Partial<StatusResult> = {},
): StatusResult {
  return {
    user_id: 'u_1',
    onboarded: true,
    timezone: 'America/Los_Angeles',
    state,
    reason_code: null,
    plan_version: 'plan_001',
    active_plan_version: null,
    draft_schedule_id: 'draft_1',
    approval_event_id: null,
    replan_kind: null,
    recovery_mode: null,
    recovery_mode_pending_user_choice: false,
    explanation: null,
    reflection: null,
    ...over,
  }
}

describe('reviewMode', () => {
  it('only awaiting_user_approval is editable (drag-to-adjust + approve)', () => {
    expect(reviewMode(status('awaiting_user_approval'))).toBe('editable')
  })

  it('a verified write and its downstream active-plan states are read-only "written"', () => {
    for (const state of [
      'calendar_write_verified',
      'active_plan',
      'drift_detected',
      'terminal_success',
    ] as const) {
      expect(reviewMode(status(state))).toBe('written')
    }
  })

  it('replan_required is its own mode — it must NEVER read as "your week is scheduled"', () => {
    expect(reviewMode(status('replan_required'))).toBe('replan')
  })

  it('the in-flight write states are read-only "writing"', () => {
    expect(reviewMode(status('calendar_write_approved'))).toBe('writing')
    expect(reviewMode(status('calendar_write_in_progress'))).toBe('writing')
  })

  it('a failed write is its own read-only mode — never editable', () => {
    expect(reviewMode(status('calendar_write_failed'))).toBe('failed')
  })

  it('a missing run (no status, or a blank pre-draft state) is not editable', () => {
    expect(reviewMode(null)).toBe('written')
    expect(reviewMode(status(null))).toBe('written')
    expect(reviewMode(status('scheduler_running'))).toBe('written')
  })
})

describe('reviewBanner', () => {
  it('the written banner points at the calendar', () => {
    expect(reviewBanner('written').sub).toContain('Google Calendar')
  })

  it('the failed banner is honest: not on the calendar, plan not activated, never "rolled back"', () => {
    const { sub } = reviewBanner('failed')
    expect(sub).toContain('aren’t confirmed')
    expect(sub).toContain('wasn’t activated')
    expect(sub.toLowerCase()).not.toContain('rolled back')
    expect(sub.toLowerCase()).not.toContain('roll back')
  })

  it('the replan banner names the typed drift cause and promises the approval gate', () => {
    const s = status('replan_required', { reason_code: 'DRIFT_DURATION_UNDERESTIMATE' })
    const { title, sub } = reviewBanner('replan', s)
    expect(title).toBe('Your plan needs an update')
    expect(sub).toContain('taking longer than planned')
    expect(sub).toContain('approval')
  })

  it('the replan banner directs to the picker when the mode choice is pending', () => {
    const s = status('replan_required', {
      reason_code: 'ACCOUNTABILITY_MISMATCH',
      recovery_mode_pending_user_choice: true,
    })
    expect(reviewBanner('replan', s).sub).toContain('Choose how to adjust')
  })
})

describe('replanReason', () => {
  it('maps every drift reason_code that can park a replan to plain language', () => {
    expect(replanReason('DRIFT_EXTERNAL_CONFLICT')).toContain('conflict')
    expect(replanReason('DRIFT_CAPACITY_MISMATCH')).toContain('time')
    expect(replanReason('ACCOUNTABILITY_MISMATCH')).toContain('pace')
    expect(replanReason('USER_RECOMMITMENT_REQUIRED')).toContain('commitment')
  })

  it('falls back honestly for unknown / missing codes', () => {
    expect(replanReason(null)).toContain('drifted')
    expect(replanReason('SOMETHING_NEW')).toContain('drifted')
  })
})

describe('RECOVERY_OPTIONS', () => {
  it('mirrors the backend RecoveryAction enum values exactly', () => {
    expect(RECOVERY_OPTIONS.map((o) => o.mode)).toEqual([
      'reschedule',
      'scope_reduction',
      'extend_timeline',
    ])
  })
})

describe('setupDeepLink', () => {
  it('time-setup failures land on the Time & constraints step', () => {
    for (const code of [
      'INSUFFICIENT_WEEKLY_CAPACITY',
      'USER_FIT_VIOLATED',
      'NO_VALID_CONTIGUOUS_BLOCK',
      'DAILY_LOAD_EXCEEDED',
      'COVERAGE_INCOMPLETE',
    ]) {
      expect(setupDeepLink(code)).toBe('/onboarding?step=1')
    }
  })

  it('everything else starts at the top of the form', () => {
    expect(setupDeepLink('LLM_REFUSAL')).toBe('/onboarding')
    expect(setupDeepLink(null)).toBe('/onboarding')
  })
})

function diff(over: Partial<PlanDiffView> = {}): PlanDiffView {
  return {
    from_plan_version: 'plan_001',
    to_plan_version: 'plan_002',
    tasks_added: 0,
    tasks_removed: 0,
    tasks_changed: 0,
    tasks_preserved: 0,
    net_load_change_min: 0,
    changes: [],
    ...over,
  }
}

describe('planDiffLine', () => {
  it('is null when there is no diff (fresh propose)', () => {
    expect(planDiffLine(null)).toBeNull()
    expect(planDiffLine(undefined)).toBeNull()
  })

  it('names only the nonzero deltas against the prior-plan total', () => {
    expect(
      planDiffLine(diff({ tasks_preserved: 14, tasks_changed: 3, tasks_added: 1 })),
    ).toBe('This update keeps 14 of 17 tasks from your current plan — 3 changed, 1 added.')
    expect(planDiffLine(diff({ tasks_preserved: 5, tasks_removed: 2 }))).toBe(
      'This update keeps 5 of 7 tasks from your current plan — 2 removed.',
    )
  })

  it('says so plainly when everything is preserved', () => {
    expect(planDiffLine(diff({ tasks_preserved: 2 }))).toBe(
      'This update keeps all 2 tasks from your current plan unchanged.',
    )
  })

  it('uses the singular for a one-task prior plan', () => {
    expect(planDiffLine(diff({ tasks_changed: 1, tasks_added: 2 }))).toBe(
      'This update keeps 0 of 1 task from your current plan — 1 changed, 2 added.',
    )
  })
})

describe('attentionChip', () => {
  it('parked states produce a chip pointing at the right screen', () => {
    expect(attentionChip('replan_required')?.to).toBe('/review')
    expect(attentionChip('calendar_write_failed')?.to).toBe('/approve')
    expect(attentionChip('error_requires_user')?.to).toBe('/plan')
  })

  it('healthy and transient states produce no chip', () => {
    for (const state of ['active_plan', 'awaiting_user_approval', 'terminal_success', null, undefined]) {
      expect(attentionChip(state)).toBeNull()
    }
  })
})
