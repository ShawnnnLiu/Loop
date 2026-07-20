import { describe, expect, it } from 'vitest'

import type { UserProfile } from '../api/types'
import { DAY_MS } from './datetime'
import {
  allowedWindowMin,
  initialScrollMin,
  nowMinutesOfDay,
  parseHHMM,
  splitBusySegments,
} from './gridtime'

const profileFixture = (before: string, after: string): UserProfile => ({
  user_id: 'u1',
  profile_version: 'v1',
  goal: 'Land a backend role',
  target_role: 'Backend SWE',
  target_companies: [],
  target_level: null,
  timeline_weeks: 12,
  weekly_hours: 10,
  experience_level: 'intermediate',
  known_strengths: [],
  known_weaknesses: [],
  experience: [],
  skills: [],
  preferred_session_length_min: 60,
  max_session_length_min: 120,
  deep_work_windows: [],
  hard_constraints: {
    no_events_before: before,
    no_events_after: after,
    allow_weekends: true,
    max_daily_study_min: 240,
    min_break_between_deep_blocks_min: 30,
  },
  preferences: {
    prefer_evening_sessions: false,
    prefer_weekend_long_blocks: false,
    avoid_back_to_back_deep_work: true,
  },
  motivation_profile_id: null,
  resume_text: null,
  plan_direction: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
})

const FALLBACK = { start: 480, end: 1380 }

describe('parseHHMM', () => {
  it('parses two-digit HH:MM values', () => {
    expect(parseHHMM('07:30')).toBe(450)
    expect(parseHHMM('00:00')).toBe(0)
    expect(parseHHMM('23:59')).toBe(1439)
  })

  it('rejects malformed or out-of-range values', () => {
    expect(parseHHMM('7:30')).toBeNull()
    expect(parseHHMM('24:00')).toBeNull()
    expect(parseHHMM('aa:bb')).toBeNull()
    expect(parseHHMM('')).toBeNull()
  })
})

describe('allowedWindowMin', () => {
  it('reads the profile hard constraints', () => {
    expect(allowedWindowMin(profileFixture('06:00', '22:00'))).toEqual({ start: 360, end: 1320 })
  })

  it('falls back to 08:00–23:00 when the profile is null', () => {
    expect(allowedWindowMin(null)).toEqual(FALLBACK)
  })

  it('falls back when either bound fails to parse', () => {
    expect(allowedWindowMin(profileFixture('6:00', '22:00'))).toEqual(FALLBACK)
    expect(allowedWindowMin(profileFixture('06:00', '25:00'))).toEqual(FALLBACK)
  })

  it('falls back on inverted or empty bounds', () => {
    expect(allowedWindowMin(profileFixture('22:00', '06:00'))).toEqual(FALLBACK)
    expect(allowedWindowMin(profileFixture('09:00', '09:00'))).toEqual(FALLBACK)
  })
})

describe('splitBusySegments', () => {
  const DAY0 = Date.UTC(2026, 6, 20)

  it('passes single-day intervals through unchanged', () => {
    const seg = { dayMs: DAY0, startMin: 600, durMin: 90 }
    expect(splitBusySegments([seg])).toEqual([seg])
    // Ending exactly at midnight is still single-day.
    expect(splitBusySegments([{ dayMs: DAY0, startMin: 1380, durMin: 60 }])).toEqual([
      { dayMs: DAY0, startMin: 1380, durMin: 60 },
    ])
  })

  it('splits a midnight-crossing interval into two clipped segments', () => {
    // 23:00–01:00 → 23:00–24:00 on day N, 00:00–01:00 on day N+1.
    expect(splitBusySegments([{ dayMs: DAY0, startMin: 1380, durMin: 120 }])).toEqual([
      { dayMs: DAY0, startMin: 1380, durMin: 60 },
      { dayMs: DAY0 + DAY_MS, startMin: 0, durMin: 60 },
    ])
  })

  it('yields one segment per day across two midnights', () => {
    // 23:00 day N → 01:00 day N+2 (26h).
    expect(splitBusySegments([{ dayMs: DAY0, startMin: 1380, durMin: 1560 }])).toEqual([
      { dayMs: DAY0, startMin: 1380, durMin: 60 },
      { dayMs: DAY0 + DAY_MS, startMin: 0, durMin: 1440 },
      { dayMs: DAY0 + 2 * DAY_MS, startMin: 0, durMin: 60 },
    ])
  })

  it('drops zero-length segments', () => {
    expect(splitBusySegments([{ dayMs: DAY0, startMin: 600, durMin: 0 }])).toEqual([])
  })
})

describe('nowMinutesOfDay', () => {
  // 2026-07-21 12:34 UTC — a fixed instant, asserted per offset.
  const NOW = Date.UTC(2026, 6, 21, 12, 34)

  it('uses the UTC wall clock for Z', () => {
    expect(nowMinutesOfDay(NOW, 'Z')).toBe(12 * 60 + 34)
  })

  it('applies positive and negative offsets', () => {
    expect(nowMinutesOfDay(NOW, '+05:30')).toBe(18 * 60 + 4)
    expect(nowMinutesOfDay(NOW, '-07:00')).toBe(5 * 60 + 34)
  })

  it('wraps when the offset crosses midnight relative to UTC', () => {
    // 01:00 UTC at -02:00 → 23:00 the previous wall-clock day.
    expect(nowMinutesOfDay(Date.UTC(2026, 6, 21, 1, 0), '-02:00')).toBe(1380)
    // 23:00 UTC at +03:00 → 02:00 the next wall-clock day.
    expect(nowMinutesOfDay(Date.UTC(2026, 6, 21, 23, 0), '+03:00')).toBe(120)
  })
})

describe('initialScrollMin', () => {
  it('scrolls above now when now precedes the allowed start', () => {
    expect(initialScrollMin(480, 300)).toBe(270)
  })

  it('scrolls above the allowed start when now is later', () => {
    expect(initialScrollMin(480, 600)).toBe(450)
  })

  it('uses the allowed start when today is not in view', () => {
    expect(initialScrollMin(480, null)).toBe(450)
  })

  it('clamps at 0 for an allowed start earlier than 00:30', () => {
    expect(initialScrollMin(10, null)).toBe(0)
  })
})
