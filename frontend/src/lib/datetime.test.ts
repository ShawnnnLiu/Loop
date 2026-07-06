import { describe, expect, it } from 'vitest'

import {
  DAY_MS,
  dayHeader,
  dayUtcMs,
  fmtAgo,
  fmtDate,
  fmtMinutes,
  isoAt,
  minutesOfDay,
  mondayIndex,
  offsetMinutes,
  parseWall,
  todayDayMs,
  windowStartMs,
} from './datetime'

describe('parseWall', () => {
  it('reads the wall-clock components and offset as written', () => {
    expect(parseWall('2026-05-04T18:00:00-07:00')).toEqual({
      y: 2026,
      mo: 5,
      d: 4,
      hh: 18,
      mm: 0,
      offset: '-07:00',
    })
  })

  it('accepts a Z offset, a +00:00 offset, and fractional seconds', () => {
    expect(parseWall('2026-05-06T19:30:00Z').offset).toBe('Z')
    expect(parseWall('2026-05-06T19:30:00+00:00').offset).toBe('+00:00')
    expect(parseWall('2026-05-06T19:30:00.123456Z')).toMatchObject({ hh: 19, mm: 30, offset: 'Z' })
  })

  it('defaults a missing offset to Z and reads minute precision', () => {
    expect(parseWall('2026-05-06T19:30')).toEqual({
      y: 2026,
      mo: 5,
      d: 6,
      hh: 19,
      mm: 30,
      offset: 'Z',
    })
  })

  it('throws on an unparseable string', () => {
    expect(() => parseWall('not-a-date')).toThrow()
  })
})

describe('week + day math (UTC, browser-tz independent)', () => {
  // 2026-05-04 is a Monday; 2026-05-06 a Wednesday; 2026-05-10 a Sunday.
  it('maps weekdays to a Monday-based index', () => {
    expect(mondayIndex(dayUtcMs(parseWall('2026-05-04T00:00:00Z')))).toBe(0) // Mon
    expect(mondayIndex(dayUtcMs(parseWall('2026-05-06T00:00:00Z')))).toBe(2) // Wed
    expect(mondayIndex(dayUtcMs(parseWall('2026-05-10T00:00:00Z')))).toBe(6) // Sun
  })
})

describe('offsetMinutes', () => {
  it('reads Z, positive, and negative offsets', () => {
    expect(offsetMinutes('Z')).toBe(0)
    expect(offsetMinutes('+00:00')).toBe(0)
    expect(offsetMinutes('+05:30')).toBe(330)
    expect(offsetMinutes('-07:00')).toBe(-420)
  })
})

describe('todayDayMs', () => {
  it("gives the user's wall-clock date, not the browser's or UTC's", () => {
    // 2026-07-05T02:00Z is still July 4 in Los Angeles (-07:00)…
    const nowMs = Date.UTC(2026, 6, 5, 2, 0)
    expect(new Date(todayDayMs(nowMs, '-07:00')).toISOString().slice(0, 10)).toBe('2026-07-04')
    // …but already July 5 in UTC and further east.
    expect(new Date(todayDayMs(nowMs, 'Z')).toISOString().slice(0, 10)).toBe('2026-07-05')
    expect(new Date(todayDayMs(nowMs, '+05:30')).toISOString().slice(0, 10)).toBe('2026-07-05')
  })
})

describe('windowStartMs (rolling 7-day windows anchored on today)', () => {
  const anchor = dayUtcMs(parseWall('2026-07-05T00:00:00Z')) // "today"

  it("puts today and the next six days in today's window", () => {
    for (let i = 0; i < 7; i++) {
      expect(windowStartMs(anchor + i * DAY_MS, anchor)).toBe(anchor)
    }
  })

  it('starts the following window exactly 7 days out', () => {
    expect(windowStartMs(anchor + 7 * DAY_MS, anchor)).toBe(anchor + 7 * DAY_MS)
    expect(windowStartMs(anchor + 13 * DAY_MS, anchor)).toBe(anchor + 7 * DAY_MS)
  })

  it('puts past days in earlier windows (negative floor)', () => {
    expect(windowStartMs(anchor - DAY_MS, anchor)).toBe(anchor - 7 * DAY_MS)
    expect(windowStartMs(anchor - 7 * DAY_MS, anchor)).toBe(anchor - 7 * DAY_MS)
    expect(windowStartMs(anchor - 8 * DAY_MS, anchor)).toBe(anchor - 14 * DAY_MS)
  })
})

describe('minutesOfDay', () => {
  it('is hours*60 + minutes', () => {
    expect(minutesOfDay(parseWall('2026-05-04T18:00:00-07:00'))).toBe(1080)
    expect(minutesOfDay(parseWall('2026-05-06T10:30:00Z'))).toBe(630)
    expect(minutesOfDay(parseWall('2026-05-06T00:00:00Z'))).toBe(0)
  })
})

describe('isoAt (reconstruct an adjusted start)', () => {
  it('preserves the offset and lands on the right day + time', () => {
    const base = dayUtcMs(parseWall('2026-05-04T18:00:00-07:00')) // window starts Mon May 4
    // Move Monday 18:00 -> Wednesday (idx 2) 10:30, same Pacific offset.
    expect(isoAt(base, 2, 630, '-07:00')).toBe('2026-05-06T10:30:00-07:00')
  })

  it('round-trips back through parseWall', () => {
    const base = dayUtcMs(parseWall('2026-05-04T09:00:00Z')) // a Monday
    const iso = isoAt(base, 4, 945, 'Z') // Friday 15:45
    const w = parseWall(iso)
    expect(mondayIndex(dayUtcMs(w))).toBe(4)
    expect(minutesOfDay(w)).toBe(945)
    expect(w.offset).toBe('Z')
  })
})

describe('fmtMinutes', () => {
  it('formats 12-hour times with a/p and drops :00', () => {
    expect(fmtMinutes(0)).toBe('12a')
    expect(fmtMinutes(8 * 60)).toBe('8a')
    expect(fmtMinutes(630)).toBe('10:30a')
    expect(fmtMinutes(12 * 60)).toBe('12p')
    expect(fmtMinutes(13 * 60 + 5)).toBe('1:05p')
    expect(fmtMinutes(23 * 60)).toBe('11p')
  })
})

describe('dayHeader', () => {
  it('labels each column from the window start', () => {
    const monday = dayUtcMs(parseWall('2026-05-04T00:00:00Z'))
    expect(dayHeader(monday, 0)).toEqual({ dow: 'Mon', label: 'May 4' })
    expect(dayHeader(monday, 2)).toEqual({ dow: 'Wed', label: 'May 6' })
    expect(dayHeader(monday, 6)).toEqual({ dow: 'Sun', label: 'May 10' })
  })

  it('uses the real weekday when the window starts mid-week (today-anchored)', () => {
    const wednesday = dayUtcMs(parseWall('2026-05-06T00:00:00Z'))
    expect(dayHeader(wednesday, 0)).toEqual({ dow: 'Wed', label: 'May 6' })
    expect(dayHeader(wednesday, 1)).toEqual({ dow: 'Thu', label: 'May 7' })
    expect(dayHeader(wednesday, 6)).toEqual({ dow: 'Tue', label: 'May 12' })
  })
})

describe('fmtDate', () => {
  it('formats the date as written, ignoring offset and time', () => {
    expect(fmtDate('2026-06-21T09:00:00Z')).toBe('Jun 21')
    expect(fmtDate('2026-05-04T23:30:00-07:00')).toBe('May 4')
    expect(fmtDate('2026-12-31T00:00:00+00:00')).toBe('Dec 31')
  })
})

describe('fmtAgo', () => {
  const T0 = Date.UTC(2026, 6, 6, 12, 0, 0)

  it('reads "just now" under a minute, including a stamp slightly ahead of now (clock skew)', () => {
    expect(fmtAgo(T0, T0)).toBe('just now')
    expect(fmtAgo(T0 - 59_000, T0)).toBe('just now')
    expect(fmtAgo(T0 + 5_000, T0)).toBe('just now')
  })

  it('switches to minutes, hours, then days at the natural boundaries', () => {
    expect(fmtAgo(T0 - 60_000, T0)).toBe('1m ago')
    expect(fmtAgo(T0 - 2 * 60_000, T0)).toBe('2m ago')
    expect(fmtAgo(T0 - 59 * 60_000, T0)).toBe('59m ago')
    expect(fmtAgo(T0 - 60 * 60_000, T0)).toBe('1h ago')
    expect(fmtAgo(T0 - 3 * 3_600_000, T0)).toBe('3h ago')
    expect(fmtAgo(T0 - 23 * 3_600_000, T0)).toBe('23h ago')
    expect(fmtAgo(T0 - 24 * 3_600_000, T0)).toBe('1d ago')
    expect(fmtAgo(T0 - 9 * DAY_MS, T0)).toBe('9d ago')
  })
})
