import { describe, expect, it } from 'vitest'

import type { DraftView, RollbackResult, WriteCycleResult } from '../api/types'
import {
  failureInfoFromRecovery,
  failureInfoFromResult,
  hasRemovableEvents,
  rollbackConfirmMessage,
  rollbackOutcomeMessage,
  shortHash,
  toWriteBlocks,
  writeFailureMessage,
  writeOutcome,
} from './approval'

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
    deleted_task_ids: [],
    plan_diff: null,
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

  it('shows a too-short input whole instead of overlapping head/tail', () => {
    expect(shortHash('abcde')).toBe('sha256:abcde') // not "abcd…cde"
  })
})

describe('writeFailureMessage', () => {
  it('a verification failure says events are flagged and the plan was not activated — never "rolled back"', () => {
    const msg = writeFailureMessage(
      writeResult({
        reason_code: 'CALENDAR_VERIFICATION_FAILED',
        planned_event_count: 6,
        written_task_ids: ['a', 'b', 'c', 'd', 'e', 'f'],
        verified_task_ids: ['a', 'b', 'c', 'd'],
        failed_task_ids: ['e', 'f'],
      }),
    )
    expect(msg).toContain('4 confirmed')
    expect(msg).toContain('2 could not be verified')
    expect(msg).toContain('plan wasn’t activated')
    expect(msg.toLowerCase()).not.toContain('rolled back')
    expect(msg.toLowerCase()).not.toContain('roll back')
  })

  it('a partial create failure reports what was created and that cleanup may be manual', () => {
    const msg = writeFailureMessage(
      writeResult({
        reason_code: 'CALENDAR_WRITE_FAILED',
        written_task_ids: ['a'],
        verified_task_ids: [],
        failed_task_ids: [],
      }),
    )
    expect(msg).toContain('1 event was created')
    expect(msg).toContain('wasn’t activated')
  })

  it('a pre-write abort (nothing written) surfaces the typed error / a safe generic', () => {
    expect(
      writeFailureMessage(writeResult({ reason_code: 'APPROVAL_HASH_MISMATCH', error: 'hash changed' })),
    ).toBe('hash changed')
    expect(writeFailureMessage(writeResult({ reason_code: 'CALENDAR_WRITE_LOCK_BUSY', error: null }))).toContain(
      'nothing was written',
    )
  })
})

function rollbackResult(over: Partial<RollbackResult> = {}): RollbackResult {
  return {
    run_id: 'r_1',
    user_id: 'u_1',
    state: 'error_requires_user',
    dry_run: false,
    rollbackable_event_count: 0,
    deleted_event_ids: [],
    failed_event_ids: [],
    fully_rolled_back: true,
    reason_code: null,
    error: null,
    ...over,
  }
}

describe('write-failure recovery helpers', () => {
  it('hasRemovableEvents: written or verification-flagged events are removable; a pre-write abort is not', () => {
    expect(hasRemovableEvents(writeResult({ written_task_ids: ['a'] }))).toBe(true)
    expect(hasRemovableEvents(writeResult({ failed_task_ids: ['a'] }))).toBe(true)
    expect(hasRemovableEvents(writeResult())).toBe(false)
  })

  it('failureInfoFromResult carries the verified pill and the removable flag', () => {
    const info = failureInfoFromResult(
      writeResult({
        reason_code: 'CALENDAR_VERIFICATION_FAILED',
        planned_event_count: 6,
        written_task_ids: ['a', 'b'],
        verified_task_ids: ['a'],
        failed_task_ids: ['b'],
      }),
    )
    expect(info.reasonCode).toBe('CALENDAR_VERIFICATION_FAILED')
    expect(info.pill).toBe('1 / 6 verified')
    expect(info.removable).toBe(true)
    expect(info.message.toLowerCase()).not.toContain('rolled back')
  })

  it('failureInfoFromRecovery (mount path) has no pill and names the leftover count', () => {
    const info = failureInfoFromRecovery('EXTERNAL_SYNC_FAILED', 3)
    expect(info.pill).toBeNull()
    expect(info.removable).toBe(true)
    expect(info.message).toContain('3 events it created are on your calendar')
    expect(info.message).toContain('wasn’t activated')

    const clean = failureInfoFromRecovery(null, 0)
    expect(clean.removable).toBe(false)
    expect(clean.message).toContain('No events from it remain')
  })

  it('rollbackConfirmMessage names the exact count and says it cannot be undone', () => {
    const msg = rollbackConfirmMessage(14)
    expect(msg).toContain('all 14 events')
    expect(msg).toContain('can’t be undone')
    expect(rollbackConfirmMessage(1)).toContain('the 1 event')
    expect(rollbackConfirmMessage(0)).toContain('No events')
  })

  it('rollbackOutcomeMessage: a full rollback reads as closed, a partial one invites another attempt', () => {
    const full = rollbackOutcomeMessage(
      rollbackResult({ deleted_event_ids: ['e1', 'e2'], fully_rolled_back: true }),
    )
    expect(full).toContain('all 2 events')
    expect(full).toContain('build a new plan')

    const partial = rollbackOutcomeMessage(
      rollbackResult({
        deleted_event_ids: ['e1'],
        failed_event_ids: ['e2'],
        fully_rolled_back: false,
        state: 'calendar_write_failed',
      }),
    )
    expect(partial).toContain('1 event')
    expect(partial).toContain('couldn’t be deleted')
    expect(partial).toContain('try removing them again')
    // A partial rollback must never read as resolved.
    expect(partial.toLowerCase()).not.toContain('back to how it was')
  })
})

describe('writeOutcome', () => {
  it('a null reason_code is a verified success', () => {
    expect(writeOutcome(writeResult({ reason_code: null, planned_event_count: 6, verified_task_ids: ['a', 'b', 'c', 'd', 'e', 'f'] }))).toBe('verified')
  })

  it('any typed reason_code is a failure — even with some events verified', () => {
    const partial = writeResult({
      reason_code: 'CALENDAR_VERIFICATION_FAILED',
      planned_event_count: 6,
      verified_task_ids: ['a', 'b', 'c', 'd'],
      failed_task_ids: ['e', 'f'],
    })
    expect(writeOutcome(partial)).toBe('failed')
  })
})
