import { describe, expect, it } from 'vitest'

import type { KnowledgeBranchView, KnowledgeMapView, KnowledgeNodeView } from '../../api/types'
import { NO_SIGNALS, type NodeSignals } from './signals'
import {
  honedFraction,
  nothingLit,
  panTransform,
  planetLabel,
  plaqueSummary,
  statusLine,
  trailArcs,
} from './render'

function sig(over: Partial<NodeSignals>): NodeSignals {
  return { ...NO_SIGNALS, ...over }
}

function node(over: Partial<KnowledgeNodeView>): KnowledgeNodeView {
  return {
    node_id: over.node_id ?? 'n',
    title: over.title ?? 'N',
    kind: over.kind ?? 'skill',
    tier: over.tier ?? 'discovered',
    group_id: over.group_id ?? 'g',
    branch: over.branch ?? null,
    skill_id: over.skill_id ?? null,
    expected_minutes: over.expected_minutes ?? null,
    blurb: over.blurb ?? null,
    description: over.description ?? null,
    note: over.note ?? null,
    linked_module_ids: over.linked_module_ids ?? [],
    is_personal: over.is_personal ?? false,
    sessions_total: over.sessions_total ?? null,
    sessions_done: over.sessions_done ?? null,
    next_session_at: over.next_session_at ?? null,
    evidence_label: over.evidence_label ?? null,
    evidence_confirmed_at: over.evidence_confirmed_at ?? null,
    review_flagged: over.review_flagged ?? false,
    self_assessed: over.self_assessed ?? false,
  }
}

describe('statusLine', () => {
  const skill = { kind: 'skill' as const, is_personal: false }

  it('reports honest tier text with no invented data', () => {
    expect(statusLine(skill, 'discovered', NO_SIGNALS)).toBe(
      'Discovered · on the map, no study yet',
    )
    expect(statusLine(skill, 'training', NO_SIGNALS)).toBe('Training · under way')
    expect(statusLine(skill, 'honed', NO_SIGNALS)).toBe('Honed')
    expect(statusLine(skill, 'proven', NO_SIGNALS)).toBe('Proven ✦')
  })

  it('adds the session count only when session data is present', () => {
    expect(statusLine(skill, 'training', sig({ sessionsTotal: 4, sessionsDone: 2 }))).toBe(
      'Training · 2 of 4 sessions',
    )
  })

  it('surfaces honed flags honestly', () => {
    expect(statusLine(skill, 'honed', sig({ reviewFlagged: true }))).toBe('Honed · review-flagged')
    expect(statusLine(skill, 'honed', sig({ reviewFlagged: true, selfAssessed: true }))).toBe(
      'Honed · review-flagged · self-assessed',
    )
  })

  it('prefixes personal nodes and never gilds them', () => {
    expect(statusLine({ kind: 'custom', is_personal: true }, 'honed', NO_SIGNALS)).toBe(
      'Yours · Honed',
    )
  })

  it('reads capstone state as slot coverage, label optional', () => {
    const cap = { kind: 'capstone' as const, is_personal: false }
    expect(statusLine(cap, 'discovered', NO_SIGNALS)).toBe('Capstone — unproven')
    expect(statusLine(cap, 'proven', NO_SIGNALS)).toBe('Capstone ✦ proven')
    expect(statusLine(cap, 'proven', sig({ evidenceLabel: 'talk.md' }))).toBe(
      'Capstone ✦ proven · talk.md',
    )
  })
})

describe('trailArcs', () => {
  it('returns nothing when the trail is null (degradation)', () => {
    expect(trailArcs(null)).toEqual([])
  })

  it('draws one arc per session, the first `done` filled', () => {
    const arcs = trailArcs({ total: 4, done: 2 })
    expect(arcs).toHaveLength(4)
    expect(arcs.map((a) => a.filled)).toEqual([true, true, false, false])
    expect(arcs[0].d).toMatch(/^M[-\d.]+ [-\d.]+A20 20 0 [01] 1 [-\d.]+ [-\d.]+$/)
  })

  it('is byte-stable across calls', () => {
    expect(trailArcs({ total: 3, done: 1 })).toEqual(trailArcs({ total: 3, done: 1 }))
  })
})

describe('planetLabel', () => {
  it('anchors side worlds outward and stacks top/bottom', () => {
    // right (cos≈1)
    expect(planetLabel(0, 100, 100, false)).toEqual({ anchor: 'start', x: 128, y: 104 })
    // left (cos≈-1)
    expect(planetLabel(Math.PI, 100, 100, false)).toEqual({ anchor: 'end', x: 72, y: 104 })
    // top (sin<0)
    expect(planetLabel(-Math.PI / 2, 100, 100, false)).toEqual({
      anchor: 'middle',
      x: 100,
      y: 74,
    })
    // bottom (sin>0)
    expect(planetLabel(Math.PI / 2, 100, 100, false)).toEqual({
      anchor: 'middle',
      x: 100,
      y: 132,
    })
  })

  it('tightens the offset for comets', () => {
    expect(planetLabel(0, 0, 0, true)).toEqual({ anchor: 'start', x: 18, y: 4 })
  })
})

describe('panTransform', () => {
  it('is identity when nothing is focused', () => {
    expect(panTransform(null, false)).toEqual({ x: 0, y: 0, k: 1 })
  })

  it('scales and never reveals the sky edges (clamped ≤ 0 and ≥ -edge)', () => {
    const p = panTransform({ x: 900, y: 285 }, true)
    expect(p.k).toBe(1.3)
    expect(p.x).toBeLessThanOrEqual(0)
    expect(p.y).toBeLessThanOrEqual(0)
    // lower bound = vis - 1180*k for x, 665 - 665*k for y
    expect(p.x).toBeGreaterThanOrEqual((1180 - 320) - 1180 * 1.3)
    expect(p.y).toBeGreaterThanOrEqual(665 - 665 * 1.3)
  })
})

describe('map aggregates', () => {
  const branch = (over: Partial<KnowledgeBranchView>): KnowledgeBranchView => ({
    slot_id: over.slot_id ?? 'b',
    title: over.title ?? 'B',
    capstone_node_id: over.capstone_node_id ?? 'cap',
    capstone_tier: over.capstone_tier ?? 'discovered',
    honed_count: over.honed_count ?? 0,
    total_count: over.total_count ?? 0,
  })

  const view: KnowledgeMapView = {
    has_selection: true,
    pathway_id: 'p',
    registry_version: 'v1',
    version_mismatch: false,
    branches: [branch({ slot_id: 'llm', capstone_tier: 'proven' }), branch({ slot_id: 'int' })],
    groups: [
      {
        group_id: 'g1',
        title: 'G1',
        branch: 'llm',
        blurb: null,
        member_node_ids: ['a', 'b'],
        honed_count: 1,
        total_count: 2,
        is_personal: false,
      },
      {
        group_id: 'gp',
        title: 'Yours',
        branch: 'personal',
        blurb: null,
        member_node_ids: ['c'],
        honed_count: 0,
        total_count: 0,
        is_personal: true,
      },
    ],
    nodes: [
      node({ node_id: 'a', tier: 'honed' }),
      node({ node_id: 'b', tier: 'proven' }),
      node({ node_id: 'c', is_personal: true, kind: 'custom', tier: 'honed' }),
      node({ node_id: 'cap', kind: 'capstone', tier: 'proven' }),
    ],
  }

  it('honedFraction counts pathway worlds only', () => {
    // 2 pathway worlds (a honed, b proven), both honed-or-above → 1.0
    expect(honedFraction(view)).toBe(1)
  })

  it('plaqueSummary reports honest totals, personal excluded', () => {
    expect(plaqueSummary(view)).toEqual({
      branches: 2,
      systems: 1,
      worlds: 2,
      capstones: 2,
      honed: 2,
      proven: 1,
      capstonesProven: 1,
    })
  })

  it('nothingLit is false once anything is lit', () => {
    expect(nothingLit(view)).toBe(false)
    const dark: KnowledgeMapView = {
      ...view,
      branches: [branch({ slot_id: 'llm' })],
      nodes: [node({ node_id: 'a', tier: 'discovered' })],
    }
    expect(nothingLit(dark)).toBe(true)
  })
})
