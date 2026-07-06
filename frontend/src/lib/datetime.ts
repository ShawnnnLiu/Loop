// Tz-safe helpers for the schedule grid. Draft entries are tz-aware ISO strings
// whose offset is the USER's timezone (the scheduler placed them there). We grid
// by the WALL-CLOCK time as written — never the browser-local conversion — and
// reconstruct adjusted starts with the SAME offset so the server reads the time
// the user intended. Week/day math runs in UTC to stay browser-tz-independent.
//
// The week grid is a rolling 7-day window anchored on TODAY (the user's
// wall-clock date): today is always the leftmost column, and paging moves in
// whole 7-day steps from that anchor — not Monday-to-Sunday calendar weeks.

export const DAY_MS = 86_400_000
const WEEK_MS = 7 * DAY_MS

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

/** Monday=0 … Sunday=6 for a UTC-midnight ms (weekday labels only — the grid
 *  itself anchors on today, not Monday). */
export function mondayIndex(dayMs: number): number {
  return (new Date(dayMs).getUTCDay() + 6) % 7
}

/** Minutes east of UTC for an ISO offset string ('Z', '+HH:MM' or '-HH:MM'). */
export function offsetMinutes(offset: string): number {
  const m = /^([+-])(\d{2}):(\d{2})$/.exec(offset)
  if (!m) return 0 // 'Z'
  const sign = m[1] === '-' ? -1 : 1
  return sign * (Number(m[2]) * 60 + Number(m[3]))
}

/** UTC-midnight ms of the wall-clock date at `nowMs` in `offset` — "today" as
 *  the user's own calendar shows it, not the browser's. */
export function todayDayMs(nowMs: number, offset: string): number {
  return Math.floor((nowMs + offsetMinutes(offset) * 60_000) / DAY_MS) * DAY_MS
}

/** UTC-midnight ms of the first day of the rolling 7-day window that contains
 *  `dayMs`, for windows anchored at `anchorMs` (today). The anchor's own window
 *  starts AT the anchor, so today is column 0; past days fall into earlier
 *  windows (Math.floor is correct for negative offsets too). */
export function windowStartMs(dayMs: number, anchorMs: number): number {
  return anchorMs + Math.floor((dayMs - anchorMs) / WEEK_MS) * WEEK_MS
}

export function minutesOfDay(w: Wall): number {
  return w.hh * 60 + w.mm
}

/** Build an ISO datetime at (window start + dayIdx, minutes-of-day), carrying
 *  `offset` so the server reads it in the user's timezone. */
export function isoAt(baseMs: number, dayIdx: number, minutes: number, offset: string): string {
  const date = new Date(baseMs + dayIdx * DAY_MS)
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

/** "Mon Apr 27" for a window start + day index, for the week header. The
 *  weekday comes from the actual date (windows anchor on today, not Monday). */
export function dayHeader(baseMs: number, dayIdx: number): { dow: string; label: string } {
  const ms = baseMs + dayIdx * DAY_MS
  const date = new Date(ms)
  const month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return {
    dow: DAY_LABELS[mondayIndex(ms)],
    label: `${month[date.getUTCMonth()]} ${date.getUTCDate()}`,
  }
}

/** "Tue Jun 23 · 10:30a" for one tz-aware ISO start, by its wall-clock time. */
export function fmtWhen(iso: string): string {
  const w = parseWall(iso)
  const head = dayHeader(dayUtcMs(w), 0)
  return `${head.dow} ${head.label} · ${fmtMinutes(minutesOfDay(w))}`
}

/** Just the wall-clock time of an ISO datetime, e.g. "11:30a". */
export function fmtClock(iso: string): string {
  return fmtMinutes(minutesOfDay(parseWall(iso)))
}

/** "Jun 23" — the date of an ISO datetime as written (no tz conversion; same
 *  as-written convention as the grid, and deterministic across browsers). */
export function fmtDate(iso: string): string {
  return dayHeader(dayUtcMs(parseWall(iso)), 0).label
}

/** Compact age of a past instant: "just now" (<1 min), then "5m ago",
 *  "3h ago", "2d ago". Instant-vs-instant, so no wall-clock/offset concerns;
 *  a `thenMs` slightly in the future (server/client clock skew) clamps to
 *  "just now" rather than going negative. */
export function fmtAgo(thenMs: number, nowMs: number): string {
  const mins = Math.max(0, Math.floor((nowMs - thenMs) / 60_000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
