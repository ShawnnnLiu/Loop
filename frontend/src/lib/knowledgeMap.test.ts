import { describe, expect, it } from 'vitest'

import type { KnowledgeGroupView, KnowledgeMapView, KnowledgeNodeView } from '../api/types'
import {
  SETTABLE_TIERS,
  branchCountLabel,
  branchGroups,
  canMarkEvidence,
  coreGroups,
  groupCountLabel,
  groupNodes,
  isMastered,
  partitionGroups,
  tierLabel,
} from './knowledgeMap'

// Additive atlas signals (SA-A) — absent/false in these view-model fixtures.
const NO_ATLAS_SIGNALS = {
  sessions_total: null,
  sessions_done: null,
  next_session_at: null,
  evidence_label: null,
  evidence_confirmed_at: null,
  review_flagged: false,
  self_assessed: false,
}

function skill(id: string, tier: KnowledgeNodeView['tier'], groupId: string): KnowledgeNodeView {
  return {
    node_id: id,
    title: id,
    kind: 'skill',
    tier,
    group_id: groupId,
    branch: null,
    skill_id: `skill.${id}`,
    expected_minutes: 300,
    blurb: null,
    description: null,
    note: null,
    linked_module_ids: [],
    is_personal: false,
    ...NO_ATLAS_SIGNALS,
  }
}

function custom(id: string, groupId: string): KnowledgeNodeView {
  return {
    node_id: id,
    title: id,
    kind: 'custom',
    tier: 'training',
    group_id: groupId,
    branch: null,
    skill_id: null,
    expected_minutes: null,
    blurb: null,
    description: 'mine',
    note: null,
    linked_module_ids: [],
    is_personal: true,
    ...NO_ATLAS_SIGNALS,
  }
}

function group(
  id: string,
  branch: string,
  members: string[],
  honed: number,
  personal = false,
): KnowledgeGroupView {
  return {
    group_id: id,
    title: id,
    branch,
    blurb: null,
    member_node_ids: members,
    honed_count: personal ? 0 : honed,
    total_count: personal ? 0 : members.length,
    is_personal: personal,
  }
}

const VIEW: KnowledgeMapView = {
  has_selection: true,
  pathway_id: 'p',
  registry_version: 'v1',
  version_mismatch: false,
  branches: [
    { slot_id: 'depth', title: 'Depth', capstone_node_id: 'kn-cap', capstone_tier: 'proven', honed_count: 1, total_count: 2 },
  ],
  groups: [
    group('kg-a', 'depth', ['kn-1', 'kn-2'], 1),
    group('kg-core', 'core', ['kn-3'], 1),
    group('kcg-p', 'personal', ['kcn-1'], 0, true),
  ],
  nodes: [
    skill('kn-1', 'honed', 'kg-a'),
    skill('kn-2', 'training', 'kg-a'),
    skill('kn-3', 'honed', 'kg-core'),
    custom('kcn-1', 'kcg-p'),
  ],
}

describe('knowledgeMap view logic', () => {
  it('tierLabel capitalizes the enum', () => {
    expect(tierLabel('honed')).toBe('Honed')
    expect(SETTABLE_TIERS).toEqual(['discovered', 'training', 'honed'])
    expect(SETTABLE_TIERS).not.toContain('proven') // evidence-gated, never settable
  })

  it('isMastered is honed-or-above only', () => {
    expect(isMastered('discovered')).toBe(false)
    expect(isMastered('training')).toBe(false)
    expect(isMastered('honed')).toBe(true)
    expect(isMastered('proven')).toBe(true)
  })

  it('group + branch count labels are honest n/m, never percentages', () => {
    expect(groupCountLabel(VIEW.groups[0])).toBe('1/2 honed')
    expect(branchCountLabel(VIEW.branches[0])).toBe('1/2 honed · capstone proven')
  })

  it('partitions the personal layer out of the pathway groups', () => {
    const { pathwayGroups, personalGroups } = partitionGroups(VIEW)
    expect(pathwayGroups.map((g) => g.group_id)).toEqual(['kg-a', 'kg-core'])
    expect(personalGroups.map((g) => g.group_id)).toEqual(['kcg-p'])
  })

  it('personal groups count toward nothing (0/0) even with members', () => {
    const personal = partitionGroups(VIEW).personalGroups[0]
    expect(personal.member_node_ids).toHaveLength(1)
    expect(groupCountLabel(personal)).toBe('0/0 honed')
  })

  it('branchGroups selects only that branch, groupNodes preserves member order', () => {
    expect(branchGroups(VIEW, 'depth').map((g) => g.group_id)).toEqual(['kg-a'])
    expect(groupNodes(VIEW, VIEW.groups[0]).map((n) => n.node_id)).toEqual(['kn-1', 'kn-2'])
  })

  it('coreGroups catches groups under no evidence-slot branch, never personal ones', () => {
    // The bug this guards: a `core` group (branch not in the branch list) must
    // still render — dropped groups made a proven node invisible.
    expect(coreGroups(VIEW).map((g) => g.group_id)).toEqual(['kg-core'])
    expect(branchGroups(VIEW, 'depth')).not.toContain(coreGroups(VIEW)[0])
  })

  it('mark-evidence is only for a honed non-personal skill node', () => {
    expect(canMarkEvidence(skill('kn-1', 'honed', 'kg-a'))).toBe(true)
    expect(canMarkEvidence(skill('kn-2', 'training', 'kg-a'))).toBe(false) // not yet honed
    expect(canMarkEvidence(custom('kcn-1', 'kcg-p'))).toBe(false) // personal, no anchor
    const capstone: KnowledgeNodeView = { ...skill('kn-cap', 'honed', 'kg-a'), kind: 'capstone', skill_id: null }
    expect(canMarkEvidence(capstone)).toBe(false) // capstone proves via its slot
  })
})
