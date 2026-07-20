import { describe, expect, it } from 'vitest'

import { popoverPlacement } from './popover'

// The real grid's geometry: 24h × 46px, card estimate 180px.
const base = { gridHeightPx: 1104, cardHeightPx: 180, hourPx: 46 }

describe('popoverPlacement', () => {
  it('opens rightward from the first five columns', () => {
    for (const dayIdx of [0, 1, 2, 3, 4]) {
      const p = popoverPlacement({ dayIdx, startMin: 600, ...base })
      expect(p.side).toBe('right')
      expect(p.leftPct).toBeCloseTo(((dayIdx + 1) / 7) * 100)
    }
  })

  it('flips leftward in the last two columns', () => {
    for (const dayIdx of [5, 6]) {
      const p = popoverPlacement({ dayIdx, startMin: 600, ...base })
      expect(p.side).toBe('left')
      expect(p.leftPct).toBeCloseTo((dayIdx / 7) * 100)
    }
  })

  it('tracks the block top in the middle of the grid', () => {
    expect(popoverPlacement({ dayIdx: 2, startMin: 600, ...base }).topPx).toBe(460)
  })

  it('clamps the top at both ends so the card stays inside the grid', () => {
    expect(popoverPlacement({ dayIdx: 2, startMin: 0, ...base }).topPx).toBe(8)
    // 23:59 → raw ~1103px; clamped to 1104 - 180 - 8.
    expect(popoverPlacement({ dayIdx: 2, startMin: 1439, ...base }).topPx).toBe(916)
  })
})
