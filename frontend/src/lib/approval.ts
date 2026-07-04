// Pure logic behind the approval gate, kept React-free so it is unit-testable
// without a DOM runner (the same split as lib/datetime.ts). The screen
// (screens/Approval.tsx) renders from these; the server remains authoritative.

import type { DraftView, RollbackResult, WriteCycleResult } from '../api/types'
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

/** Honest, server-truth message for a failed write. The engine does NOT
 *  auto-roll back — on a verification failure it marks the unverified events
 *  VERIFICATION_FAILED and leaves them on the calendar, and the plan is not
 *  activated. So the copy never claims a rollback: it states what landed, what
 *  didn't, and points at the two explicit recovery actions the card offers. */
export function writeFailureMessage(result: WriteCycleResult): string {
  const verified = result.verified_task_ids.length
  const failed = result.failed_task_ids.length
  if (failed > 0) {
    return (
      `${verified} confirmed; ${failed} could not be verified after writing. ` +
      `The unverified ${failed === 1 ? 'event is' : 'events are'} flagged on your ` +
      `calendar and your plan wasn’t activated. You can retry the missing events ` +
      `or remove everything this write created.`
    )
  }
  if (result.written_task_ids.length > 0) {
    const n = result.written_task_ids.length
    return (
      `${n} ${n === 1 ? 'event was' : 'events were'} created but the write didn’t ` +
      `finish, so your plan wasn’t activated. You can retry the missing events ` +
      `or remove everything this write created.`
    )
  }
  return result.error ?? 'The write didn’t complete; nothing was written and your plan wasn’t activated.'
}

/** True when the failed write left recovery-worthy work behind: something was
 *  written (removable) or verification flagged events. A pre-write abort
 *  (nothing written) still offers retry, but "remove written events" would be
 *  an empty gesture — hide it. */
export function hasRemovableEvents(result: WriteCycleResult): boolean {
  return result.written_task_ids.length > 0 || result.failed_task_ids.length > 0
}

/** Everything the failed-write recovery card renders, regardless of how the
 *  screen learned about the failure — a write that just failed in-session
 *  (full WriteCycleResult) or a run found already parked in
 *  calendar_write_failed on mount (status + rollback dry-run count). */
export interface WriteFailureInfo {
  reasonCode: string | null
  /** "N / M verified" pill; null when the counts aren't known (mount path). */
  pill: string | null
  message: string
  removable: boolean
}

export function failureInfoFromResult(result: WriteCycleResult): WriteFailureInfo {
  return {
    reasonCode: result.reason_code,
    pill: `${result.verified_task_ids.length} / ${result.planned_event_count} verified`,
    message: writeFailureMessage(result),
    removable: hasRemovableEvents(result),
  }
}

export function failureInfoFromRecovery(
  reasonCode: string | null,
  removableCount: number,
): WriteFailureInfo {
  const remains =
    removableCount > 0
      ? `${removableCount} ${removableCount === 1 ? 'event it created is' : 'events it created are'} on your calendar. `
      : 'No events from it remain on your calendar. '
  return {
    reasonCode,
    pill: null,
    message:
      `A previous write to your calendar didn’t complete, so your plan wasn’t activated. ` +
      remains +
      'You can retry the missing events or remove what was written.',
    removable: removableCount > 0,
  }
}

/** Copy for the rollback confirmation dialog — a destructive external action,
 *  so it names the exact count the server reported via the dry-run. */
export function rollbackConfirmMessage(count: number): string {
  if (count === 0) {
    return 'No events from this write remain on your calendar. Confirming will just close out this plan attempt.'
  }
  return (
    `This deletes ${count === 1 ? 'the 1 event' : `all ${count} events`} this write ` +
    `created on your Google Calendar. Your other calendar events are untouched. ` +
    `This can’t be undone — the plan attempt ends and you can build a new one.`
  )
}

/** Honest outcome copy after a rollback ran. A partial rollback keeps the run
 *  recoverable server-side, so the copy must invite another attempt rather
 *  than read as resolved. */
export function rollbackOutcomeMessage(result: RollbackResult): string {
  const deleted = result.deleted_event_ids.length
  const failedCount = result.failed_event_ids.length
  if (result.fully_rolled_back) {
    return deleted === 0
      ? 'Nothing was left on your calendar to remove. This plan attempt is closed — build a new plan when you’re ready.'
      : `Removed ${deleted === 1 ? 'the 1 event' : `all ${deleted} events`} this write created. ` +
          'Your calendar is back to how it was — build a new plan when you’re ready.'
  }
  return (
    `Removed ${deleted}, but ${failedCount} ${failedCount === 1 ? 'event' : 'events'} ` +
    `couldn’t be deleted${result.error ? ` (${result.error})` : ''}. ` +
    'Nothing is lost — you can try removing them again.'
  )
}
