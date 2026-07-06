// Pure logic behind the Accountability screen's interactive cards (B3),
// React-free and unit-tested like lib/review.ts. The engine owns semantics:
// choices are typed enums the server maps deterministically; this module only
// carries the plain-language copy and the outcome messaging.

import type { RecommitChoice, RecommitResult, WeeklyCheckinResult } from '../api/types'

export interface RecommitChoiceOption {
  choice: RecommitChoice
  title: string
  description: string
}

/** The four typed answers to "can you recommit to this plan?" — mirrors the
 *  backend RecommitmentChoice enum. revise_timeline / revise_intensity map
 *  deterministically onto replans; keep_plan records re-approval; revise_goal
 *  records the intent and points at onboarding. */
export const RECOMMIT_CHOICES: RecommitChoiceOption[] = [
  {
    choice: 'keep_plan',
    title: 'Keep my plan',
    description: 'I can recommit to the current plan as it stands.',
  },
  {
    choice: 'revise_timeline',
    title: 'Give me more time',
    description: 'Keep the full plan and spread it over more weeks.',
  },
  {
    choice: 'revise_intensity',
    title: 'Reduce the load',
    description: 'Trim the plan so it fits the time I actually have.',
  },
  {
    choice: 'revise_goal',
    title: 'My goal changed',
    description: 'Revisit the goal itself in your setup.',
  },
]

/** Honest outcome copy per answer. A replan-parking choice must say a draft is
 *  coming for review — never that the plan already changed. */
export function recommitOutcomeMessage(result: RecommitResult): string {
  if (result.replan_required) {
    const how =
      result.recovery_mode === 'extend_timeline'
        ? 'spread over more weeks'
        : result.recovery_mode === 'scope_reduction'
          ? 'with a lighter load'
          : 'adjusted'
    return `Got it. Loop will draft an updated plan ${how} — review and approve it on the Week screen; nothing changes until you do.`
  }
  if (result.choice === 'keep_plan') {
    return 'Recommitment recorded — the plan stands as-is. Keep checking tasks off in Today.'
  }
  if (result.choice === 'revise_goal') {
    return 'Recorded. When your goal itself changes, update it in your setup — Loop will build a fresh plan from there.'
  }
  return 'Recorded.'
}

/** Copy after submitting the weekly check-in — names the server-computed
 *  counts so the user sees exactly what was recorded. */
export function weeklyCheckinOutcomeMessage(result: WeeklyCheckinResult): string {
  return (
    `Week recorded: ${result.completed_task_count} of ${result.scheduled_task_count} ` +
    `scheduled ${result.scheduled_task_count === 1 ? 'task' : 'tasks'} completed.`
  )
}
