import { describe, expect, it } from 'vitest'

import type { StatusResult } from '../api/types'
import { reviewBanner, reviewMode } from './review'

function status(state: StatusResult['state']): StatusResult {
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
      'replan_required',
      'terminal_success',
    ] as const) {
      expect(reviewMode(status(state))).toBe('written')
    }
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
})
