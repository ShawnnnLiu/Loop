// Pure logic behind the approval gate, kept React-free so it is unit-testable
// without a DOM runner (the same split as lib/datetime.ts). The screen
// (screens/Approval.tsx) renders from these; the server remains authoritative.

import type { DraftView, WriteCycleResult } from '../api/types'
import { fmtWhen } from './datetime'

export interface WriteBlock {
  taskId: string
  title: string
  when: string // "Mon Jun 23 · 4p"
  sortKey: number // ms, for chronological order
}

/** Draft entries -> chronological, human-labeled rows for the confirm list. */
export function toWriteBlocks(view: DraftView): WriteBlock[] {
  const titles = view.task_titles
  return (view.draft?.entries ?? [])
    .map((entry) => ({
      taskId: entry.task_id,
      title: titles[entry.task_id] ?? entry.task_id,
      when: fmtWhen(entry.start),
      sortKey: Date.parse(entry.start),
    }))
    .sort((a, b) => a.sortKey - b.sortKey)
}

/** Truncate a canonical payload hash for display, e.g. "sha256:9f3a…c4d".
 *  Production hashes are 64 hex chars; for an input too short to truncate
 *  without the head and tail overlapping, show it whole rather than mislead. */
export function shortHash(hash: string | null): string {
  if (!hash) return 'sha256:—'
  const hex = hash.startsWith('sha256:') ? hash.slice(7) : hash
  if (hex.length <= 7) return `sha256:${hex}`
  return `sha256:${hex.slice(0, 4)}…${hex.slice(-3)}`
}

/** The one invariant the gate UI encodes: a write that returns a typed
 *  reason_code FAILED; only a null reason_code is a verified success. A partial
 *  verified/planned count is therefore still a failure, never a success. */
export function writeOutcome(result: WriteCycleResult): 'verified' | 'failed' {
  return result.reason_code ? 'failed' : 'verified'
}

/** Honest, server-truth message for a failed write. The MVP does NOT auto-roll
 *  back — on a verification failure the engine marks the unverified events
 *  VERIFICATION_FAILED and leaves them on the calendar, and the plan is not
 *  activated (there is no user-facing undo; that endpoint was deferred). So the
 *  copy never claims a rollback: it states what landed, what didn't, and that
 *  cleanup may be manual. */
export function writeFailureMessage(result: WriteCycleResult): string {
  const verified = result.verified_task_ids.length
  const failed = result.failed_task_ids.length
  if (failed > 0) {
    const them = failed === 1 ? 'it' : 'them'
    return (
      `${verified} confirmed; ${failed} could not be verified after writing. ` +
      `The unverified ${failed === 1 ? 'event is' : 'events are'} flagged on your ` +
      `calendar and your plan wasn’t activated — you may need to remove ${them} manually.`
    )
  }
  if (result.written_task_ids.length > 0) {
    const n = result.written_task_ids.length
    return (
      `${n} ${n === 1 ? 'event was' : 'events were'} created but the write didn’t ` +
      `finish, so your plan wasn’t activated. Check your calendar — you may need to ` +
      `remove ${n === 1 ? 'it' : 'them'}.`
    )
  }
  return result.error ?? 'The write didn’t complete; nothing was written and your plan wasn’t activated.'
}
