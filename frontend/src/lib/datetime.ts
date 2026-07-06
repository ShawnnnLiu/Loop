// Tz-safe helpers for the schedule grid. Draft entries are tz-aware ISO strings
// whose offset is the USER's timezone (the scheduler placed them there). We grid
// by the WALL-CLOCK time as written — never the browser-local conversion — and
// reconstruct adjusted starts with the SAME offset so the server reads the time
// the user intended. Week/day math runs in UTC to stay browser-tz-independent.

const DAY_MS = 86_400_000

export interface Wall {
  y: number
  mo: number // 1-12
  d: number
  hh: number
  mm: number
  offset: string // 'Z' or '+HH:MM' / '-HH:MM'
}

const ISO_RE =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$/

export function parseWall(iso: string): Wall {
  const m = ISO_RE.exec(iso)
  if (!m) throw new Error(`unparseable datetime: ${iso}`)
  return {
    y: Number(m[1]),
    mo: Number(m[2]),
    d: Number(m[3]),
    hh: Number(m[4]),
    mm: Number(m[5]),
    offset: m[7] ?? 'Z',
  }
}

const pad = (n: number) => String(n).padStart(2, '0')

/** UTC midnight of the wall date — a stable key for day/week arithmetic. */
export function dayUtcMs(w: Wall): number {
  return Date.UTC(w.y, w.mo - 1, w.d)
}

/** Monday=0 … Sunday=6 for a UTC-midnight ms. */
export function mondayIndex(dayMs: number): number {
  return (new Date(dayMs).getUTCDay() + 6) % 7
}

/** UTC-midnight ms of the Monday that starts this date's week. */
export function weekMondayMs(dayMs: number): number {
  return dayMs - mondayIndex(dayMs) * DAY_MS
}

export function minutesOfDay(w: Wall): number {
  return w.hh * 60 + w.mm
}

/** Build an ISO datetime at (week Monday + dayIdx, minutes-of-day), carrying
 *  `offset` so the server reads it in the user's timezone. */
export function isoAt(mondayMs: number, dayIdx: number, minutes: number, offset: string): string {
  const date = new Date(mondayMs + dayIdx * DAY_MS)
  const hh = Math.floor(minutes / 60)
  const mm = minutes % 60
  return (
    `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}` +
    `T${pad(hh)}:${pad(mm)}:00${offset}`
  )
}

/** Short label for a minutes-of-day value, e.g. 630 -> "10:30a". */
export function fmtMinutes(minutes: number): string {
  let h = Math.floor(minutes / 60)
  const m = minutes % 60
  const ap = h >= 12 ? 'p' : 'a'
  h = h % 12 || 12
  return m === 0 ? `${h}${ap}` : `${h}:${pad(m)}${ap}`
}

export const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const

/** "Mon Apr 27" for a week-Monday + day index, for the week header. */
export function dayHeader(mondayMs: number, dayIdx: number): { dow: string; label: string } {
  const date = new Date(mondayMs + dayIdx * DAY_MS)
  const month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return { dow: DAY_LABELS[dayIdx], label: `${month[date.getUTCMonth()]} ${date.getUTCDate()}` }
}

/** "Tue Jun 23 · 10:30a" for one tz-aware ISO start, by its wall-clock time. */
export function fmtWhen(iso: string): string {
  const w = parseWall(iso)
  const dayMs = dayUtcMs(w)
  const head = dayHeader(weekMondayMs(dayMs), mondayIndex(dayMs))
  return `${head.dow} ${head.label} · ${fmtMinutes(minutesOfDay(w))}`
}

/** Just the wall-clock time of an ISO datetime, e.g. "11:30a". */
export function fmtClock(iso: string): string {
  return fmtMinutes(minutesOfDay(parseWall(iso)))
}

/** "Jun 23" — the date of an ISO datetime as written (no tz conversion; same
 *  as-written convention as the grid, and deterministic across browsers). */
export function fmtDate(iso: string): string {
  const w = parseWall(iso)
  const dayMs = dayUtcMs(w)
  return dayHeader(weekMondayMs(dayMs), mondayIndex(dayMs)).label
}
