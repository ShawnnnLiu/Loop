import { describe, expect, it } from 'vitest'

import { CONFIDENCE_OPTIONS, checkinBody } from './checkin'

describe('checkin confidence triage', () => {
  it('offers exactly the three design-decision options in order', () => {
    expect(CONFIDENCE_OPTIONS.map((o) => o.value)).toEqual(['confident', 'unsure', 'needed_help'])
    expect(CONFIDENCE_OPTIONS.map((o) => o.label)).toEqual(['Got it', 'Shaky', 'Needed help'])
  })

  it('attaches solve_confidence to a completion when chosen', () => {
    expect(checkinBody('t1', 'complete', 'unsure')).toEqual({
      task_id: 't1',
      outcome: 'complete',
      solve_confidence: 'unsure',
    })
  })

  it('omits solve_confidence when the triage is skipped', () => {
    expect(checkinBody('t1', 'complete')).toEqual({ task_id: 't1', outcome: 'complete' })
  })

  it('never sends confidence on a miss (backend rejects it there)', () => {
    // A miss carries no confidence even if a value is somehow passed.
    expect(checkinBody('t1', 'missed', 'confident')).toEqual({ task_id: 't1', outcome: 'missed' })
  })
})
