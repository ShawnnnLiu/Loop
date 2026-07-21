// MM-B: the optional one-tap solve-confidence triage shown at Today check-off.
//
// After "Complete" the row reveals "How did it go?" with these three chips plus a
// Skip. The choice rides on the single /checkin POST as `solve_confidence`; Skip
// (or any non-completion) sends no signal, which the engine treats as neutral —
// never a penalty. Copy is the design decision from `08-mastery-memory.md` (m2).

export type SolveConfidence = 'confident' | 'unsure' | 'needed_help'

export interface ConfidenceOption {
  value: SolveConfidence
  label: string
}

export const CONFIDENCE_OPTIONS: readonly ConfidenceOption[] = [
  { value: 'confident', label: 'Got it' },
  { value: 'unsure', label: 'Shaky' },
  { value: 'needed_help', label: 'Needed help' },
]

/** The request body for a check-in; `solve_confidence` is omitted when skipped. */
export function checkinBody(
  taskId: string,
  outcome: 'complete' | 'missed',
  confidence?: SolveConfidence,
): Record<string, unknown> {
  const body: Record<string, unknown> = { task_id: taskId, outcome }
  // Only a completion can carry confidence (backend rejects it on a miss); Skip
  // leaves it out entirely rather than sending an empty value.
  if (outcome === 'complete' && confidence) body.solve_confidence = confidence
  return body
}
