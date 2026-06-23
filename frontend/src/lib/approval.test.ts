import { describe, expect, it } from 'vitest'

import type { DraftView, WriteCycleResult } from '../api/types'
import { shortHash, toWriteBlocks, writeOutcome } from './approval'

function draftView(over: Partial<DraftView> = {}): DraftView {
  return {
    draft: {
      draft_schedule_id: 'draft_1',
      plan_version: 'plan_001',
      entries: [],
    },
    payload_hash: 'sha256:9f3a1bc4d',
    hash_canonicalization_version: 'v1',
    free_busy: [],
    task_titles: {},
    ...over,
  }
}

function writeResult(over: Partial<WriteCycleResult> = {}): WriteCycleResult {
  return {
    run_id: 'r_1',
    user_id: 'u_1',
    state: 'completed',
    dry_run: false,
    write_status: 'written',
    reason_code: null,
    planned_event_count: 0,
    written_task_ids: [],
    verified_task_ids: [],
    failed_task_ids: [],
    mapping_status_by_task: {},
    error: null,
    ...over,
  }
}

describe('toWriteBlocks', () => {
  it('labels entries by wall-clock and sorts them chronologically', () => {
    const view = draftView({
      task_titles: { t_a: 'Graphs drill', t_b: 'Mock interview' },
      draft: {
        draft_schedule_id: 'draft_1',
        plan_version: 'plan_001',
        entries: [
          { task_id: 't_b', start: '2026-06-24T16:00:00-07:00', end: '2026-06-24T17:00:00-07:00', calendar_event_status: 'pending' },
          { task_id: 't_a', start: '2026-06-23T10:30:00-07:00', end: '2026-06-23T11:30:00-07:00', calendar_event_status: 'pending' },
        ],
      },
    })

    const blocks = toWriteBlocks(view)

    expect(blocks.map((b) => b.taskId)).toEqual(['t_a', 't_b']) // earlier first
    expect(blocks[0].title).toBe('Graphs drill')
    expect(blocks[0].when).toBe('Tue Jun 23 · 10:30a') // wall-clock, not browser-local
    expect(blocks[1].when).toBe('Wed Jun 24 · 4p')
  })

  it('falls back to the task_id when no title is known, and handles an empty draft', () => {
    const view = draftView({
      draft: {
        draft_schedule_id: 'draft_1',
        plan_version: 'plan_001',
        entries: [{ task_id: 't_x', start: '2026-06-23T09:00:00Z', end: '2026-06-23T10:00:00Z', calendar_event_status: 'pending' }],
      },
    })
    expect(toWriteBlocks(view)[0].title).toBe('t_x')
    expect(toWriteBlocks(draftView({ draft: null }))).toEqual([])
  })
})

describe('shortHash', () => {
  it('truncates a sha256 payload hash', () => {
    expect(shortHash('sha256:9f3a1bc4d')).toBe('sha256:9f3a…c4d')
  })

  it('handles a bare hex digest and a missing hash', () => {
    expect(shortHash('abcdef1234')).toBe('sha256:abcd…234')
    expect(shortHash(null)).toBe('sha256:—')
  })
})

describe('writeOutcome', () => {
  it('a null reason_code is a verified success', () => {
    expect(writeOutcome(writeResult({ reason_code: null, planned_event_count: 6, verified_task_ids: ['a', 'b', 'c', 'd', 'e', 'f'] }))).toBe('verified')
  })

  it('any typed reason_code is a failure — even with some events verified (auto-rolled-back)', () => {
    const partial = writeResult({
      reason_code: 'CALENDAR_VERIFICATION_FAILED',
      planned_event_count: 6,
      verified_task_ids: ['a', 'b', 'c', 'd'],
      failed_task_ids: ['e', 'f'],
    })
    expect(writeOutcome(partial)).toBe('failed')
  })
})
