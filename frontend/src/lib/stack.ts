// Google-Calendar-style column layout for overlapping blocks in a day column.
// Overlaps are legitimate display states, not errors: an adopted external move
// may sit on top of another block or a busy interval (ADR-0009), so the grid
// stacks the events side-by-side instead of drawing a collision. Pure and
// deterministic (React-free, unit-tested), the same split as the other lib/
// modules.

export interface StackItem {
  /** Stable identity for looking the slot back up at render time. */
  key: string
  startMin: number
  endMin: number
}

export interface StackSlot {
  /** 0-based column inside the overlap cluster. */
  col: number
  /** Total columns in the cluster — every member renders at width 1/cols. */
  cols: number
}

/** Assign side-by-side columns to the blocks of ONE day column.
 *
 *  Blocks are grouped into overlap clusters (maximal runs of transitively
 *  overlapping blocks); within a cluster each block takes the lowest column
 *  that is free at its start, and every member of the cluster shares the
 *  cluster's column count so widths line up. Non-overlapping blocks stay
 *  full-width (`cols: 1`). Deterministic: sorted by start, then longer first,
 *  then key. */
export function stackLayout(items: StackItem[]): Map<string, StackSlot> {
  const sorted = [...items].sort(
    (a, b) =>
      a.startMin - b.startMin || b.endMin - a.endMin || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0),
  )
  const slots = new Map<string, StackSlot>()

  let cluster: { key: string; col: number }[] = []
  let columnEnds: number[] = [] // per-column furthest end within the open cluster
  const closeCluster = () => {
    const cols = Math.max(1, columnEnds.length)
    for (const member of cluster) slots.set(member.key, { col: member.col, cols })
    cluster = []
    columnEnds = []
  }

  for (const item of sorted) {
    // Nothing in the open cluster reaches this block: the cluster is complete.
    if (columnEnds.length > 0 && columnEnds.every((end) => end <= item.startMin)) {
      closeCluster()
    }
    let col = columnEnds.findIndex((end) => end <= item.startMin)
    if (col === -1) {
      col = columnEnds.length
      columnEnds.push(item.endMin)
    } else {
      columnEnds[col] = item.endMin
    }
    cluster.push({ key: item.key, col })
  }
  closeCluster()
  return slots
}

/** `stackLayout` per day column: items carry which day they sit in; keys must
 *  be unique across the whole set. */
export function stackByDay(items: (StackItem & { dayIdx: number })[]): Map<string, StackSlot> {
  const slots = new Map<string, StackSlot>()
  const days = new Set(items.map((item) => item.dayIdx))
  for (const day of days) {
    const dayItems = items.filter((item) => item.dayIdx === day)
    for (const [key, slot] of stackLayout(dayItems)) slots.set(key, slot)
  }
  return slots
}
