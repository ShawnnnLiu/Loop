// Pure helpers for the full-day (0:00–24:00) schedule grid: the user's allowed
// scheduling window from the profile's hard constraints, midnight-splitting for
// imported busy intervals, and the wall-clock "now" minute for the current-time
// line and the initial scroll position. All day-minute values are
// minutes-of-day in the USER's wall clock (the grid's existing convention).
// React-free and unit-tested, same split as lib/stack.ts / lib/weekplan.ts.

import type { UserProfile } from '../api/types'
import { DAY_MS, offsetMinutes } from './datetime'

const MIN_PER_DAY = 1440

/** The visual bounds the grid had before the 24h rework — used as the allowed
 *  window whenever the profile can't supply one. */
const FALLBACK_WINDOW = { start: 8 * 60, end: 23 * 60 }

/** "07:30" -> 450; null for anything unparseable. */
export function parseHHMM(s: string): number | null {
  const m = /^(\d{2}):(\d{2})$/.exec(s)
  if (!m) return null
  const hh = Number(m[1])
  const mm = Number(m[2])
  if (hh > 23 || mm > 59) return null
  return hh * 60 + mm
}

/** The user's allowed scheduling window in minutes-of-day, from
 *  hard_constraints.no_events_before/after. Falls back to 08:00–23:00 (the
 *  pre-rework visual bounds) when the profile is null, either bound fails to
 *  parse, or the bounds are inverted — the backend validator forbids inverted
 *  bounds, but this helper must not trust that. */
export function allowedWindowMin(profile: UserProfile | null): { start: number; end: number } {
  if (!profile) return { ...FALLBACK_WINDOW }
  const start = parseHHMM(profile.hard_constraints.no_events_before)
  const end = parseHHMM(profile.hard_constraints.no_events_after)
  if (start == null || end == null || start >= end) return { ...FALLBACK_WINDOW }
  return { start, end }
}

export interface BusySegment {
  dayMs: number
  startMin: number
  durMin: number
}

/** Split busy intervals that cross midnight into per-day segments, each
 *  clipped to [0, 1440]. Single-day intervals pass through unchanged; an
 *  interval spanning more than one midnight yields one segment per day.
 *  Zero-length segments are dropped. */
export function splitBusySegments(busy: BusySegment[]): BusySegment[] {
  const out: BusySegment[] = []
  for (const seg of busy) {
    let dayMs = seg.dayMs
    let startMin = seg.startMin
    let durMin = seg.durMin
    while (durMin > 0 && startMin < MIN_PER_DAY) {
      const chunk = Math.min(durMin, MIN_PER_DAY - startMin)
      out.push({ dayMs, startMin, durMin: chunk })
      durMin -= chunk
      dayMs += DAY_MS
      startMin = 0
    }
  }
  return out
}

/** Minutes-of-day of `nowMs` in the user's wall clock (ISO offset string, the
 *  same source todayDayMs uses — never the browser timezone). */
export function nowMinutesOfDay(nowMs: number, offset: string): number {
  return Math.floor(((nowMs + offsetMinutes(offset) * 60_000) % DAY_MS) / 60_000)
}

/** Where to scroll on first grid render, in minutes-of-day: ~30min above
 *  min(allowed start, now) when today is in view (`nowMin` non-null), else
 *  above the allowed start. Clamped to >= 0. */
export function initialScrollMin(allowedStart: number, nowMin: number | null): number {
  return Math.max(0, Math.min(allowedStart, nowMin ?? allowedStart) - 30)
}
