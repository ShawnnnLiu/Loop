import { describe, expect, it } from 'vitest'

import type { RecommitResult, WeeklyCheckinResult } from '../api/types'
import {
  RECOMMIT_CHOICES,
  recommitOutcomeMessage,
  weeklyCheckinOutcomeMessage,
} from './accountability'

function recommitResult(over: Partial<RecommitResult> = {}): RecommitResult {
  return {
    user_id: 'u_1',
    recommitment_request_id: 'req_1',
    recommitment_event_id: 'evt_1',
    choice: 'keep_plan',
    recovery_mode: null,
    replan_required: false,
    state: 'active_plan',
    ...over,
  }
}

describe('RECOMMIT_CHOICES', () => {
  it('mirrors the backend RecommitmentChoice enum values exactly', () => {
    expect(RECOMMIT_CHOICES.map((c) => c.choice)).toEqual([
      'keep_plan',
      'revise_timeline',
      'revise_intensity',
      'revise_goal',
    ])
  })
})

describe('recommitOutcomeMessage', () => {
  it('a replan-parking answer promises a DRAFT for review — never a silent change', () => {
    const msg = recommitOutcomeMessage(
      recommitResult({
        choice: 'revise_intensity',
        recovery_mode: 'scope_reduction',
        replan_required: true,
        state: 'replan_required',
      }),
    )
    expect(msg).toContain('lighter load')
    expect(msg).toContain('review and approve')
    expect(msg).toContain('nothing changes until you do')
  })

  it('extend-timeline answers name the adjustment', () => {
    const msg = recommitOutcomeMessage(
      recommitResult({
        choice: 'revise_timeline',
        recovery_mode: 'extend_timeline',
        replan_required: true,
      }),
    )
    expect(msg).toContain('more weeks')
  })

  it('keep_plan and revise_goal record without promising a replan', () => {
    expect(recommitOutcomeMessage(recommitResult({ choice: 'keep_plan' }))).toContain(
      'plan stands',
    )
    expect(recommitOutcomeMessage(recommitResult({ choice: 'revise_goal' }))).toContain('setup')
  })
})

describe('weeklyCheckinOutcomeMessage', () => {
  it('names the server-computed counts', () => {
    const result: WeeklyCheckinResult = {
      user_id: 'u_1',
      checkin_id: 'c_1',
      checkin_status: 'completed',
      week_start: '2026-06-28',
      week_end: '2026-07-04',
      scheduled_task_count: 5,
      completed_task_count: 3,
    }
    expect(weeklyCheckinOutcomeMessage(result)).toBe(
      'Week recorded: 3 of 5 scheduled tasks completed.',
    )
  })
})
