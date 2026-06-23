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

/** Truncate a canonical payload hash for display, e.g. "sha256:9f3a…c1d". */
export function shortHash(hash: string | null): string {
  if (!hash) return 'sha256:—'
  const hex = hash.startsWith('sha256:') ? hash.slice(7) : hash
  return `sha256:${hex.slice(0, 4)}…${hex.slice(-3)}`
}

/** The one invariant the gate UI encodes: a write that returns a typed
 *  reason_code FAILED (the engine already auto-rolled-back the unverified
 *  events); only a null reason_code is a verified success. A partial
 *  verified/planned count is therefore still a failure, never a success. */
export function writeOutcome(result: WriteCycleResult): 'verified' | 'failed' {
  return result.reason_code ? 'failed' : 'verified'
}
