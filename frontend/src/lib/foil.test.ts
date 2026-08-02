import { describe, expect, it } from 'vitest'

import {
  FOIL_REST,
  clamp,
  computeFoilTarget,
  edgeDistance,
  lerp,
  smoothstep,
} from './foil'

// A 120x40 button at (100, 200), matching the .btn footprint.
const rect = { left: 100, top: 200, width: 120, height: 40 }
const center = { x: 160, y: 220 }
const opts = { maxTilt: 10, falloff: 260 }

describe('clamp / lerp / smoothstep', () => {
  it('clamps to both bounds', () => {
    expect(clamp(-2, -1, 1)).toBe(-1)
    expect(clamp(2, -1, 1)).toBe(1)
    expect(clamp(0.5, -1, 1)).toBe(0.5)
  })

  it('lerp moves proportionally toward the target', () => {
    expect(lerp(0, 10, 0.1)).toBeCloseTo(1)
    expect(lerp(5, 5, 0.1)).toBe(5)
  })

  it('smoothstep hits its edges and eases in between', () => {
    expect(smoothstep(0, 260, 0)).toBe(0)
    expect(smoothstep(0, 260, 260)).toBe(1)
    expect(smoothstep(0, 260, 400)).toBe(1)
    const mid = smoothstep(0, 260, 130)
    expect(mid).toBeCloseTo(0.5)
  })
})

describe('edgeDistance', () => {
  it('is zero anywhere inside the rect', () => {
    expect(edgeDistance(rect, center.x, center.y)).toBe(0)
    expect(edgeDistance(rect, rect.left, rect.top)).toBe(0)
  })

  it('measures straight-line distance past an edge', () => {
    expect(edgeDistance(rect, rect.left - 30, center.y)).toBe(30)
    expect(edgeDistance(rect, center.x, rect.top + rect.height + 50)).toBe(50)
  })

  it('measures diagonal distance past a corner', () => {
    expect(edgeDistance(rect, rect.left - 30, rect.top - 40)).toBe(50)
  })
})

describe('computeFoilTarget', () => {
  it('rests when the cursor is gone', () => {
    expect(computeFoilTarget(rect, null, opts)).toEqual(FOIL_REST)
  })

  it('rests when the rect has no size (display: none)', () => {
    expect(computeFoilTarget({ ...rect, width: 0 }, center, opts)).toEqual(FOIL_REST)
  })

  it('is full strength, untilted, shine centered at dead center', () => {
    const t = computeFoilTarget(rect, center, opts)
    expect(t.strength).toBe(1)
    expect(t.rx).toBeCloseTo(0)
    expect(t.ry).toBeCloseTo(0)
    expect(t.px).toBe(50)
    expect(t.py).toBe(50)
  })

  it('tilts toward the cursor and pushes the shine the same way', () => {
    const t = computeFoilTarget(rect, { x: center.x + 30, y: center.y - 10 }, opts)
    expect(t.ry).toBeGreaterThan(0)
    expect(t.rx).toBeGreaterThan(0)
    expect(t.px).toBeGreaterThan(50)
    expect(t.py).toBeLessThan(50)
  })

  it('clamps tilt at the edge but keeps direction beyond it', () => {
    const inside = computeFoilTarget(rect, { x: rect.left + rect.width, y: center.y }, opts)
    expect(inside.ry).toBeCloseTo(opts.maxTilt)
    const outside = computeFoilTarget(rect, { x: rect.left + rect.width + 40, y: center.y }, opts)
    expect(outside.ry).toBeGreaterThan(0)
    expect(outside.ry).toBeLessThan(opts.maxTilt)
  })

  it('fades strength continuously to zero across the falloff radius', () => {
    const near = computeFoilTarget(rect, { x: rect.left - 40, y: center.y }, opts)
    const far = computeFoilTarget(rect, { x: rect.left - 200, y: center.y }, opts)
    const gone = computeFoilTarget(rect, { x: rect.left - 261, y: center.y }, opts)
    expect(near.strength).toBeGreaterThan(far.strength)
    expect(far.strength).toBeGreaterThan(0)
    expect(gone.strength).toBe(0)
    expect(gone).toEqual(FOIL_REST)
  })

  it('never exceeds max tilt no matter where the cursor is', () => {
    for (const p of [
      { x: rect.left - 250, y: rect.top - 250 },
      { x: rect.left + rect.width + 5, y: rect.top + rect.height + 5 },
      { x: center.x, y: rect.top - 1 },
    ]) {
      const t = computeFoilTarget(rect, p, opts)
      expect(Math.abs(t.rx)).toBeLessThanOrEqual(opts.maxTilt)
      expect(Math.abs(t.ry)).toBeLessThanOrEqual(opts.maxTilt)
    }
  })
})
