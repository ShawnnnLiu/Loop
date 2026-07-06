import { describe, expect, it } from 'vitest'

import { stackByDay, stackLayout } from './stack'

const item = (key: string, startMin: number, endMin: number) => ({ key, startMin, endMin })

describe('stackLayout', () => {
  it('keeps non-overlapping blocks full width', () => {
    const slots = stackLayout([item('a', 540, 600), item('b', 600, 660), item('c', 720, 780)])
    expect(slots.get('a')).toEqual({ col: 0, cols: 1 })
    expect(slots.get('b')).toEqual({ col: 0, cols: 1 })
    expect(slots.get('c')).toEqual({ col: 0, cols: 1 })
  })

  it('splits two overlapping blocks side-by-side', () => {
    const slots = stackLayout([item('a', 540, 600), item('b', 570, 630)])
    expect(slots.get('a')).toEqual({ col: 0, cols: 2 })
    expect(slots.get('b')).toEqual({ col: 1, cols: 2 })
  })

  it('shares the cluster width across a transitive overlap chain', () => {
    // a overlaps b, b overlaps c, but a and c do not touch: one cluster, and c
    // reuses column 0 (free once a has ended) — GCal-style packing.
    const slots = stackLayout([item('a', 540, 600), item('b', 570, 630), item('c', 600, 660)])
    expect(slots.get('a')).toEqual({ col: 0, cols: 2 })
    expect(slots.get('b')).toEqual({ col: 1, cols: 2 })
    expect(slots.get('c')).toEqual({ col: 0, cols: 2 })
  })

  it('grows to three columns when three blocks share an instant', () => {
    const slots = stackLayout([item('a', 540, 660), item('b', 540, 660), item('c', 540, 660)])
    expect(slots.get('a')).toEqual({ col: 0, cols: 3 })
    expect(slots.get('b')).toEqual({ col: 1, cols: 3 })
    expect(slots.get('c')).toEqual({ col: 2, cols: 3 })
  })

  it('is deterministic on identical times (ordered by key)', () => {
    const forward = stackLayout([item('a', 540, 600), item('b', 540, 600)])
    const reversed = stackLayout([item('b', 540, 600), item('a', 540, 600)])
    expect(forward.get('a')).toEqual({ col: 0, cols: 2 })
    expect(forward.get('b')).toEqual({ col: 1, cols: 2 })
    expect(reversed).toEqual(forward)
  })

  it('separates clusters: a later pair does not widen an earlier solo block', () => {
    const slots = stackLayout([item('solo', 480, 540), item('x', 600, 660), item('y', 630, 690)])
    expect(slots.get('solo')).toEqual({ col: 0, cols: 1 })
    expect(slots.get('x')).toEqual({ col: 0, cols: 2 })
    expect(slots.get('y')).toEqual({ col: 1, cols: 2 })
  })

  it('handles an empty day', () => {
    expect(stackLayout([]).size).toBe(0)
  })
})

describe('stackByDay', () => {
  it('stacks per day column — same times on different days never interact', () => {
    const slots = stackByDay([
      { ...item('mon-a', 540, 600), dayIdx: 0 },
      { ...item('mon-b', 570, 630), dayIdx: 0 },
      { ...item('tue-a', 540, 600), dayIdx: 1 },
    ])
    expect(slots.get('mon-a')).toEqual({ col: 0, cols: 2 })
    expect(slots.get('mon-b')).toEqual({ col: 1, cols: 2 })
    expect(slots.get('tue-a')).toEqual({ col: 0, cols: 1 })
  })
})
