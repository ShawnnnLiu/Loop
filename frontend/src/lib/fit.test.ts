import { describe, expect, it } from 'vitest'

import type { Violation } from '../api/types'
import { formatViolation, formatViolations } from './fit'

function violation(type: string, details: Record<string, unknown> = {}): Violation {
  return { type, task_id: null, module_id: null, details }
}

describe('formatViolation', () => {
  it('spells out a weekly-load overrun in hours with the budget breakdown', () => {
    const line = formatViolation(
      violation('weekly_load_exceeds_capacity', {
        total_plan_min: 8400, // 140h
        capacity_min: 5760, // 96h
        timeline_weeks: 10,
        weekly_hours: 8,
      }),
    )
    expect(line).toBe(
      'The plan needs about 140h but your budget is about 96h (10 weeks × 8h/week). ' +
        'Raise weekly hours, extend the timeline, or narrow the goal.',
    )
  })

  it('omits the breakdown when weeks/hours are missing', () => {
    const line = formatViolation(
      violation('weekly_load_exceeds_capacity', { total_plan_min: 6000, capacity_min: 5760 }),
    )
    expect(line).toBe(
      'The plan needs about 100h but your budget is about 96h. ' +
        'Raise weekly hours, extend the timeline, or narrow the goal.',
    )
  })

  it('keeps one decimal for small-hour totals', () => {
    const line = formatViolation(
      violation('weekly_load_exceeds_capacity', { total_plan_min: 330, capacity_min: 300 }),
    )
    expect(line).toContain('about 5.5h')
    expect(line).toContain('about 5h')
  })

  it('names the oversized block against the max session', () => {
    expect(
      formatViolation(
        violation('duration_exceeds_user_max_session', {
          duration_min: 180,
          max_session_length_min: 120,
        }),
      ),
    ).toBe('A 180-min block is longer than your 120-min max session. Raise your max session length.')
  })

  it('flags a too-short block against the preferred session', () => {
    expect(
      formatViolation(
        violation('duration_far_from_preferred', {
          duration_min: 20,
          preferred_session_length_min: 60,
        }),
      ),
    ).toBe('A 20-min block is well under your preferred 60-min session. Lower your preferred session length.')
  })

  it('reports a cognitive-load out-of-range value', () => {
    expect(formatViolation(violation('cognitive_load_out_of_range', { cognitive_load: 7 }))).toBe(
      "A task's cognitive load (7) is outside the allowed 1–5 range.",
    )
  })

  it('returns null for unknown types and for missing numeric fields', () => {
    expect(formatViolation(violation('module_coverage_missing', { module_id: 'm1' }))).toBeNull()
    expect(formatViolation(violation('duration_exceeds_user_max_session', {}))).toBeNull()
  })
})

describe('formatViolations', () => {
  it('drops unknowns and de-duplicates identical lines, preserving order', () => {
    const lines = formatViolations([
      violation('duration_exceeds_user_max_session', { duration_min: 180, max_session_length_min: 120 }),
      violation('module_coverage_missing', {}),
      violation('duration_exceeds_user_max_session', { duration_min: 180, max_session_length_min: 120 }),
      violation('weekly_load_exceeds_capacity', { total_plan_min: 8400, capacity_min: 5760 }),
    ])
    expect(lines).toHaveLength(2)
    expect(lines[0]).toContain('180-min block')
    expect(lines[1]).toContain('140h')
  })

  it('returns an empty list when nothing is explainable', () => {
    expect(formatViolations([violation('task_graph_invalid')])).toEqual([])
  })
})
