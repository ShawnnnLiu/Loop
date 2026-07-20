// Placement math for the block-details popover, kept pure and unit-tested
// (React-free, same split as the other lib/ modules). No dependency: the
// 7-column grid makes placement simple enough that a positioning library
// would be overhead.

export interface PopoverPlacement {
  leftPct: number
  topPx: number
  side: 'right' | 'left'
}

/** Placement for a card anchored to a block in the 7-column grid.
 *  side: open toward the right unless the block sits in the last two columns;
 *  leftPct is the adjacent column edge (the card itself applies a small gap
 *  and, for `left`, a translateX(-100%)); top: the block's top, clamped so an
 *  estimated card height stays inside the grid body. */
export function popoverPlacement(input: {
  dayIdx: number // 0..6
  startMin: number // block top, minutes-of-day
  gridHeightPx: number
  cardHeightPx: number // estimate, e.g. 180
  hourPx: number
}): PopoverPlacement {
  const side = input.dayIdx >= 5 ? 'left' : 'right'
  const leftPct = ((side === 'right' ? input.dayIdx + 1 : input.dayIdx) / 7) * 100
  const topPx = Math.max(
    8,
    Math.min(input.gridHeightPx - input.cardHeightPx - 8, (input.startMin / 60) * input.hourPx),
  )
  return { leftPct, topPx, side }
}
