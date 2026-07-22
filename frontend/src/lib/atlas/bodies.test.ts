import { describe, expect, it } from 'vitest'

import type { KnowledgeBranchView, KnowledgeGroupView, KnowledgeNodeView, MasteryTier } from '../../api/types'
import {
  DUST_FAR,
  DUST_NEAR,
  beaconFor,
  bodyFor,
  dustLayer,
  seededRng,
  starFor,
  starRadius,
  warmthColor,
} from './bodies'
import { NO_SIGNALS, type NodeSignals } from './signals'

function nodeStub(
  overrides: Partial<Pick<KnowledgeNodeView, 'kind' | 'is_personal' | 'note'>> = {},
): Pick<KnowledgeNodeView, 'kind' | 'is_personal' | 'note'> {
  return { kind: 'skill', is_personal: false, note: null, ...overrides }
}

function sig(overrides: Partial<NodeSignals> = {}): NodeSignals {
  return { ...NO_SIGNALS, ...overrides }
}

describe('bodyFor — tier → celestial body (01-…)', () => {
  it('discovered: barren rock with the dashed chalk outline, no ornaments', () => {
    const b = bodyFor(nodeStub(), 'discovered', sig())
    expect(b.shape).toBe('rock')
    expect(b.discoveredOutline).toBe(true)
    expect(b.magmaCracks).toBe(false)
    expect(b.emberHalo).toBe(false)
    expect(b.crowned).toBe(false)
    expect(b.trail).toBeNull()
  })

  it('training: rock with magma cracks + ember halo; trail only when sessions present', () => {
    const base = bodyFor(nodeStub(), 'training', sig())
    expect(base.shape).toBe('rock')
    expect(base.magmaCracks).toBe(true)
    expect(base.emberHalo).toBe(true)
    expect(base.discoveredOutline).toBe(false)
    expect(base.trail).toBeNull() // no session signal → base training planet, no arc

    const trailed = bodyFor(nodeStub(), 'training', sig({ sessionsTotal: 4, sessionsDone: 2 }))
    expect(trailed.trail).toEqual({ total: 4, done: 2 })
  })

  it('honed: living ocean world, no crown', () => {
    const b = bodyFor(nodeStub(), 'honed', sig())
    expect(b.shape).toBe('ocean')
    expect(b.crowned).toBe(false)
    expect(b.magmaCracks).toBe(false)
  })

  it('proven: crowned ocean world', () => {
    const b = bodyFor(nodeStub(), 'proven', sig())
    expect(b.shape).toBe('ocean')
    expect(b.crowned).toBe(true)
  })

  it('review shimmer rides on honed/proven only (never lowers or invents a tier)', () => {
    expect(bodyFor(nodeStub(), 'honed', sig({ reviewFlagged: true })).reviewShimmer).toBe(true)
    expect(bodyFor(nodeStub(), 'proven', sig({ reviewFlagged: true })).reviewShimmer).toBe(true)
    // A shaky flag with no mastery is not a honed world — no shimmer.
    expect(bodyFor(nodeStub(), 'training', sig({ reviewFlagged: true })).reviewShimmer).toBe(false)
  })

  it('personal nodes are comets at every tier — never rock/ocean, never crowned/trailed', () => {
    for (const tier of ['discovered', 'training', 'honed', 'proven'] as MasteryTier[]) {
      const comet = bodyFor(nodeStub({ is_personal: true, kind: 'custom' }), tier, sig({ sessionsTotal: 3, sessionsDone: 1 }))
      expect(comet.shape).toBe('comet')
      expect(comet.crowned).toBe(false)
      expect(comet.trail).toBeNull()
      expect(comet.magmaCracks).toBe(false)
    }
    // A comet warms (teal core) once it reaches honed, but never gilds.
    expect(bodyFor(nodeStub({ is_personal: true }), 'training', sig()).cometWarmed).toBe(false)
    expect(bodyFor(nodeStub({ is_personal: true }), 'honed', sig()).cometWarmed).toBe(true)
  })

  it('the ✎ note glyph shows only for a non-empty note', () => {
    expect(bodyFor(nodeStub({ note: 'reread the paper' }), 'honed', sig()).hasNote).toBe(true)
    expect(bodyFor(nodeStub({ note: '   ' }), 'honed', sig()).hasNote).toBe(false)
    expect(bodyFor(nodeStub({ note: null }), 'honed', sig()).hasNote).toBe(false)
  })
})

describe('starFor — group brightness/warmth by honest fraction k', () => {
  function group(honed: number, total: number, personal = false): Pick<KnowledgeGroupView, 'honed_count' | 'total_count' | 'is_personal'> {
    return { honed_count: honed, total_count: total, is_personal: personal }
  }
  const members = (...tiers: MasteryTier[]) => tiers.map((tier) => ({ tier }))

  it('k is the honed fraction; 0 for an empty or personal group', () => {
    expect(starFor(group(2, 5), members()).k).toBeCloseTo(0.4)
    expect(starFor(group(0, 0), members()).k).toBe(0)
    expect(starFor(group(3, 3, true), members()).k).toBe(0) // personal counts nothing
  })

  it('brightness is monotonic in k: radius, glow and warmth all rise', () => {
    const cold = starFor(group(0, 4), members())
    const warm = starFor(group(2, 4), members())
    const hot = starFor(group(4, 4), members())
    expect(warm.radius).toBeGreaterThan(cold.radius)
    expect(hot.radius).toBeGreaterThan(warm.radius)
    expect(hot.glowOpacity).toBeGreaterThan(warm.glowOpacity)
    // colour warms toward star-gold (red channel climbs from 176 to 244)
    const red = (c: string) => Number(c.slice(4, c.indexOf(',')))
    expect(red(warm.color)).toBeGreaterThan(red(cold.color))
    expect(red(hot.color)).toBeGreaterThan(red(warm.color))
  })

  it('custom stars are chalk, fixed-radius, and never warm', () => {
    const s = starFor(group(0, 0, true), members('honed', 'honed'))
    expect(s.custom).toBe(true)
    expect(s.color).toBe('var(--chalk)')
    expect(s.radius).toBe(3)
    expect(s.crossFlareLength).toBeNull()
    expect(s.allHoned).toBe(false) // personal groups never light the constellation
  })

  it('emberPulse when any member is training; allHoned only when every member is honed', () => {
    expect(starFor(group(1, 3), members('training', 'honed', 'discovered')).emberPulse).toBe(true)
    expect(starFor(group(2, 2), members('honed', 'proven')).emberPulse).toBe(false)
    expect(starFor(group(2, 2), members('honed', 'proven')).allHoned).toBe(true)
    expect(starFor(group(1, 2), members('honed', 'training')).allHoned).toBe(false)
  })

  it('warmthColor / starRadius are pure and monotonic, clamped to [0,1]', () => {
    expect(warmthColor(0)).toBe('rgb(176,192,209)')
    expect(warmthColor(1)).toBe('rgb(244,206,138)')
    expect(warmthColor(-5)).toBe(warmthColor(0))
    expect(warmthColor(5)).toBe(warmthColor(1))
    expect(starRadius(0, false)).toBeLessThan(starRadius(1, false))
    expect(starRadius(0.9, true)).toBe(3)
  })
})

describe('beaconFor — capstone slot coverage', () => {
  function branch(tier: MasteryTier): Pick<KnowledgeBranchView, 'capstone_tier'> {
    return { capstone_tier: tier }
  }
  it('proven only at capstone_tier === proven; label matches', () => {
    expect(beaconFor(branch('proven'))).toEqual({ proven: true, label: 'CAPSTONE ✦ PROVEN' })
    for (const tier of ['discovered', 'training', 'honed'] as MasteryTier[]) {
      expect(beaconFor(branch(tier))).toEqual({ proven: false, label: 'CAPSTONE — UNPROVEN' })
    }
  })
})

describe('seeded dust — deterministic star field', () => {
  it('seededRng is a pure, reproducible sequence', () => {
    const a = seededRng(7)
    const b = seededRng(7)
    const seqA = [a(), a(), a(), a()]
    const seqB = [b(), b(), b(), b()]
    expect(seqA).toEqual(seqB)
    expect(seqA.every((v) => v >= 0 && v < 1)).toBe(true)
  })

  it('dustLayer is byte-stable for a given seed and honest to its count', () => {
    expect(dustLayer(7, 95, 0.5, 0.6, 0.3)).toEqual(dustLayer(7, 95, 0.5, 0.6, 0.3))
    expect(DUST_NEAR).toHaveLength(95)
    expect(DUST_FAR).toHaveLength(45)
    // different seeds → different fields
    expect(dustLayer(7, 10, 0.5, 0.6, 0.3)).not.toEqual(dustLayer(23, 10, 0.5, 0.6, 0.3))
  })

  it('every mote is inside the canonical viewBox', () => {
    for (const m of DUST_NEAR) {
      expect(m.x).toBeGreaterThanOrEqual(20)
      expect(m.x).toBeLessThanOrEqual(1160)
      expect(m.y).toBeGreaterThanOrEqual(16)
      expect(m.y).toBeLessThanOrEqual(648)
    }
  })
})
