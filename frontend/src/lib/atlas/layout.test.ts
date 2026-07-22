import { describe, expect, it } from 'vitest'

import type {
  KnowledgeBranchView,
  KnowledgeGroupView,
  KnowledgeMapView,
  KnowledgeNodeView,
} from '../../api/types'
import { CANONICAL_VIEWPORT, layoutSky } from './layout'

// ——— fixture builders (tiers/counts are irrelevant to layout, so kept minimal) ———

let nodeCounter = 0
function nodeIds(groupId: string, count: number): string[] {
  return Array.from({ length: count }, () => `${groupId}-n${nodeCounter++}`)
}

function group(
  id: string,
  branch: string,
  memberCount: number,
  personal = false,
): { group: KnowledgeGroupView; nodes: KnowledgeNodeView[] } {
  const members = nodeIds(id, memberCount)
  return {
    group: {
      group_id: id,
      title: id,
      branch,
      blurb: null,
      member_node_ids: members,
      honed_count: 0,
      total_count: personal ? 0 : memberCount,
      is_personal: personal,
    },
    nodes: members.map((nid) => ({
      node_id: nid,
      title: nid,
      kind: personal ? 'custom' : 'skill',
      tier: 'discovered',
      group_id: id,
      branch: null,
      skill_id: null,
      expected_minutes: null,
      blurb: null,
      description: null,
      note: null,
      linked_module_ids: [],
      is_personal: personal,
      sessions_total: null,
      sessions_done: null,
      next_session_at: null,
      evidence_label: null,
      evidence_confirmed_at: null,
      review_flagged: false,
      self_assessed: false,
    })),
  }
}

function branch(slotId: string): KnowledgeBranchView {
  return {
    slot_id: slotId,
    title: slotId,
    capstone_node_id: `cap-${slotId}`,
    capstone_tier: 'discovered',
    honed_count: 0,
    total_count: 0,
  }
}

function assemble(
  branches: KnowledgeBranchView[],
  parts: ReturnType<typeof group>[],
): KnowledgeMapView {
  return {
    has_selection: true,
    pathway_id: 'p',
    registry_version: 'v1',
    version_mismatch: false,
    branches,
    groups: parts.map((p) => p.group),
    nodes: parts.flatMap((p) => p.nodes),
  }
}

/** The reference pathway — the demo's shape: 3 evidence slots (llm/int/pub),
 *  their systems, a core group, and a personal group. */
function referenceView(): KnowledgeMapView {
  nodeCounter = 0
  return assemble(
    [branch('llm'), branch('int'), branch('pub')],
    [
      group('kg-retr', 'llm', 3),
      group('kg-prompt', 'llm', 2),
      group('kg-rel', 'llm', 3),
      group('kg-serve', 'int', 3),
      group('kg-prod', 'int', 2),
      group('kg-story', 'pub', 2),
      group('kg-found', 'core', 2),
      group('kg-side', 'personal', 2, true),
    ],
  )
}

function separation(sky: ReturnType<typeof layoutSky>): number {
  const s = sky.systems
  let min = Infinity
  for (let i = 0; i < s.length; i++) {
    for (let j = i + 1; j < s.length; j++) {
      min = Math.min(min, Math.hypot(s[i].x - s[j].x, s[i].y - s[j].y))
    }
  }
  return min
}

const LEGIBILITY = 96

describe('layoutSky — determinism', () => {
  it('is a pure function: same view → deep-equal output (incl. planet accessors)', () => {
    const a = layoutSky(referenceView())
    const b = layoutSky(referenceView())
    expect(a.systems).toEqual(b.systems)
    expect(a.capstones).toEqual(b.capstones)
    expect(a.regions).toEqual(b.regions)
    expect(a.planetsFor('kg-retr')).toEqual(b.planetsFor('kg-retr'))
  })

  it('reference systems are byte-stable (committed snapshot / regression guard)', () => {
    const sky = layoutSky(referenceView())
    // The force sim's fixed seeds + fixed ITER + rounding make this exact; this
    // snapshot is the regression guard against any accidental jitter.
    expect(sky.systems).toMatchInlineSnapshot(`
      [
        {
          "groupId": "kg-prompt",
          "x": 337.6,
          "y": 351.3,
        },
        {
          "groupId": "kg-rel",
          "x": 206.8,
          "y": 328.4,
        },
        {
          "groupId": "kg-retr",
          "x": 293.7,
          "y": 239,
        },
        {
          "groupId": "kg-prod",
          "x": 964.1,
          "y": 287.3,
        },
        {
          "groupId": "kg-serve",
          "x": 852.9,
          "y": 307.5,
        },
        {
          "groupId": "kg-story",
          "x": 589.1,
          "y": 186.6,
        },
        {
          "groupId": "kg-found",
          "x": 592.1,
          "y": 448.6,
        },
        {
          "groupId": "kg-side",
          "x": 961.6,
          "y": 587.4,
        },
      ]
    `)
  })
})

describe('layoutSky — composition fidelity (reference echoes the hero)', () => {
  it('every reference system settles inside its seeded region ellipse', () => {
    const view = referenceView()
    const sky = layoutSky(view)
    const branchOf = new Map(view.groups.map((g) => [g.group_id, g.branch]))
    const regionByBranch = new Map(sky.regions.map((r) => [r.branch, r]))
    // core groups (branch not a slot) map to the 'core' region
    const slotIds = new Set(view.branches.map((b) => b.slot_id))

    for (const s of sky.systems) {
      const b = branchOf.get(s.groupId)!
      if (b === 'personal') continue // personal has no nebula
      const regionKey = slotIds.has(b) ? b : 'core'
      const r = regionByBranch.get(regionKey)!
      const norm = ((s.x - r.cx) / r.rx) ** 2 + ((s.y - r.cy) / r.ry) ** 2
      expect(norm, `${s.groupId} outside its ${regionKey} region`).toBeLessThanOrEqual(1)
    }
  })

  it('the branch → region clustering matches the demo (llm left, int right, pub top)', () => {
    const sky = layoutSky(referenceView())
    const region = (b: string) => sky.regions.find((r) => r.branch === b)!
    expect(region('llm').cx).toBeLessThan(region('int').cx) // llm left of int
    expect(region('pub').cy).toBeLessThan(region('llm').cy) // pub above the flanks
  })
})

describe('layoutSky — shape sweep (odd real maps stay legible)', () => {
  // Within the Loop pathway budget (06-…: ~40 nodes / ~8 groups); every fixture
  // must separate cleanly with no grid fallback.
  const branchCounts = [1, 2, 3, 4, 5, 6]
  const memberCounts = [2, 4, 6, 8]

  for (const n of branchCounts) {
    for (const m of memberCounts) {
      it(`n=${n} branches, ${m} members/group: separated, in-rim, one position each`, () => {
        nodeCounter = 0
        const branches = Array.from({ length: n }, (_, i) => branch(`b${i}`))
        // spread ~8 groups across the branches, plus a core + a personal group
        const perBranch = Math.max(1, Math.round(8 / n))
        const parts: ReturnType<typeof group>[] = []
        branches.forEach((b, bi) => {
          for (let g = 0; g < perBranch; g++) parts.push(group(`b${bi}-g${g}`, b.slot_id, m))
        })
        parts.push(group('core-g', 'core', m))
        parts.push(group('mine-g', 'personal', m, true))
        const view = assemble(branches, parts)
        const sky = layoutSky(view)

        expect(sky.usedGridFallback).toBe(false)
        expect(separation(sky)).toBeGreaterThanOrEqual(LEGIBILITY)
        // one position per group, all inside the rim
        expect(new Set(sky.systems.map((s) => s.groupId)).size).toBe(view.groups.length)
        for (const s of sky.systems) {
          expect(s.x).toBeGreaterThanOrEqual(40)
          expect(s.x).toBeLessThanOrEqual(CANONICAL_VIEWPORT.w - 40)
          expect(s.y).toBeGreaterThanOrEqual(40)
          expect(s.y).toBeLessThanOrEqual(CANONICAL_VIEWPORT.h - 40)
        }
        // one capstone per non-core branch
        expect(sky.capstones.map((c) => c.nodeId).sort()).toEqual(
          branches.map((b) => b.capstone_node_id).sort(),
        )
      })
    }
  }

  it('open planets keep the legibility separation up to the 8-member budget', () => {
    nodeCounter = 0
    const parts = [group('kg', 'b0', 8)]
    const view = assemble([branch('b0')], parts)
    const sky = layoutSky(view, CANONICAL_VIEWPORT, new Set(['kg']))
    const planets = sky.planetsFor('kg')
    let min = Infinity
    for (let i = 0; i < planets.length; i++) {
      for (let j = i + 1; j < planets.length; j++) {
        min = Math.min(min, Math.hypot(planets[i].x - planets[j].x, planets[i].y - planets[j].y))
      }
    }
    expect(min).toBeGreaterThanOrEqual(40)
  })
})

describe('layoutSky — order stability', () => {
  it('shuffling view.nodes / view.groups input order changes no coordinate', () => {
    const view = referenceView()
    const shuffled: KnowledgeMapView = {
      ...view,
      groups: [...view.groups].reverse(),
      nodes: [...view.nodes].reverse(),
    }
    const a = layoutSky(view)
    const b = layoutSky(shuffled)
    // systems come out in canonical (sorted) order regardless of input order
    expect([...a.systems].sort((x, y) => x.groupId.localeCompare(y.groupId))).toEqual(
      [...b.systems].sort((x, y) => x.groupId.localeCompare(y.groupId)),
    )
    expect(a.planetsFor('kg-retr')).toEqual(b.planetsFor('kg-retr'))
  })
})

describe('layoutSky — collapsed vs open planets', () => {
  it('collapsed → all members at the star centre; open → spread on the orbit ring', () => {
    const view = referenceView()
    const closed = layoutSky(view)
    const star = closed.systems.find((s) => s.groupId === 'kg-retr')!
    for (const p of closed.planetsFor('kg-retr')) {
      expect(p.x).toBe(star.x)
      expect(p.y).toBe(star.y)
      expect(p.angle).toBe(0)
    }

    const open = layoutSky(view, CANONICAL_VIEWPORT, new Set(['kg-retr']))
    const openStar = open.systems.find((s) => s.groupId === 'kg-retr')!
    const planets = open.planetsFor('kg-retr')
    expect(planets).toHaveLength(3)
    // every member sits ~ORBIT_R (64) from the star centre, at a distinct angle
    for (const p of planets) {
      expect(Math.hypot(p.x - openStar.x, p.y - openStar.y)).toBeCloseTo(64, 0)
    }
    expect(new Set(planets.map((p) => p.angle)).size).toBe(3)
  })
})

describe('layoutSky — degenerate & over-budget', () => {
  it('no branches / no groups → empty sky, no fallback', () => {
    const view = assemble([], [])
    const sky = layoutSky(view)
    expect(sky.systems).toEqual([])
    expect(sky.capstones).toEqual([])
    expect(sky.personalHeader).toBeNull()
    expect(sky.usedGridFallback).toBe(false)
  })

  it('a deliberately over-budget map falls back to the loud grid (never scrambled)', () => {
    nodeCounter = 0
    // Far past the ~8-group budget: 60 groups the sim cannot separate to 96px.
    const b = branch('b0')
    const parts = Array.from({ length: 60 }, (_, i) => group(`g${i}`, 'b0', 2))
    const view = assemble([b], parts)
    const sky = layoutSky(view)
    expect(sky.usedGridFallback).toBe(true)
    // still one position per group, still inside the rim — a legible grid
    expect(sky.systems).toHaveLength(60)
    for (const s of sky.systems) {
      expect(s.x).toBeGreaterThanOrEqual(40)
      expect(s.y).toBeGreaterThanOrEqual(40)
    }
  })
})

describe('layoutSky — viewport scaling', () => {
  it('scales canonical coordinates into a same-aspect viewport', () => {
    const view = referenceView()
    const canonical = layoutSky(view)
    const half = layoutSky(view, { w: 590, h: 332.5 })
    const a = canonical.systems.find((s) => s.groupId === 'kg-retr')!
    const b = half.systems.find((s) => s.groupId === 'kg-retr')!
    expect(b.x).toBeCloseTo(a.x / 2, 0)
    expect(b.y).toBeCloseTo(a.y / 2, 0)
  })
})
