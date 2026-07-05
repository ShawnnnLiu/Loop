import { describe, expect, it } from 'vitest'

import {
  dayHeader,
  dayUtcMs,
  fmtDate,
  fmtMinutes,
  isoAt,
  minutesOfDay,
  mondayIndex,
  parseWall,
  weekMondayMs,
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

  it('snaps every day of a week to the same Monday', () => {
    const monday = weekMondayMs(dayUtcMs(parseWall('2026-05-04T18:00:00-07:00')))
    for (const iso of ['2026-05-04T08:00:00Z', '2026-05-06T19:00:00Z', '2026-05-10T23:00:00Z']) {
      expect(weekMondayMs(dayUtcMs(parseWall(iso)))).toBe(monday)
    }
    expect(new Date(monday).toISOString().slice(0, 10)).toBe('2026-05-04')
  })

  it('puts the next week on a different Monday', () => {
    const w1 = weekMondayMs(dayUtcMs(parseWall('2026-05-06T10:00:00Z')))
    const w2 = weekMondayMs(dayUtcMs(parseWall('2026-05-13T10:00:00Z')))
    expect(w2 - w1).toBe(7 * 86_400_000)
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
    const monday = weekMondayMs(dayUtcMs(parseWall('2026-05-04T18:00:00-07:00')))
    // Move Monday 18:00 -> Wednesday (idx 2) 10:30, same Pacific offset.
    expect(isoAt(monday, 2, 630, '-07:00')).toBe('2026-05-06T10:30:00-07:00')
  })

  it('round-trips back through parseWall', () => {
    const monday = weekMondayMs(dayUtcMs(parseWall('2026-05-04T09:00:00Z')))
    const iso = isoAt(monday, 4, 945, 'Z') // Friday 15:45
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
  it('labels each column from the week Monday', () => {
    const monday = weekMondayMs(dayUtcMs(parseWall('2026-05-04T00:00:00Z')))
    expect(dayHeader(monday, 0)).toEqual({ dow: 'Mon', label: 'May 4' })
    expect(dayHeader(monday, 2)).toEqual({ dow: 'Wed', label: 'May 6' })
    expect(dayHeader(monday, 6)).toEqual({ dow: 'Sun', label: 'May 10' })
  })
})

describe('fmtDate', () => {
  it('formats the date as written, ignoring offset and time', () => {
    expect(fmtDate('2026-06-21T09:00:00Z')).toBe('Jun 21')
    expect(fmtDate('2026-05-04T23:30:00-07:00')).toBe('May 4')
    expect(fmtDate('2026-12-31T00:00:00+00:00')).toBe('Dec 31')
  })
})
