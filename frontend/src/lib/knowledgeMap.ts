// Pure view-model logic for the knowledge map (KT-D). React-free and unit-tested,
// same split as lib/story.ts — every value here is a projection of the narrative
// map_state kernel's output (server-computed tiers, honest member counts), never
// an LLM signal and never a score. The map is a presentation/memory layer that
// gates nothing (axiom-11 non-interference); this module only shapes what the
// deterministic view already carries.

import type {
  KnowledgeBranchView,
  KnowledgeGroupView,
  KnowledgeMapView,
  KnowledgeNodeView,
  MasteryTier,
} from '../api/types'
import { MASTERY_TIERS } from '../api/types'

/** Human label for a tier (the raw enum is lowercase). */
export function tierLabel(tier: MasteryTier): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1)
}

/** One-line meaning of each tier, shown in the node drawer. Honest about what
 *  "honed" claims (the work happened OR the user said so) vs "proven" (artifact). */
export const TIER_MEANING: Record<MasteryTier, string> = {
  discovered: 'On the map, no work logged yet.',
  training: 'Study is scheduled or under way.',
  honed: 'The planned study minutes are complete — or you marked it done.',
  proven: 'Honed, with a real artifact you confirmed.',
}

/** A node is mastered (counts toward the honed tally) when its tier is ≥ honed.
 *  Mirrors the server's `_MASTERED_TIERS` — `proven ⊃ honed`. */
export function isMastered(tier: MasteryTier): boolean {
  return MASTERY_TIERS.indexOf(tier) >= MASTERY_TIERS.indexOf('honed')
}

/** The honest group count chip: "2/5 honed" over pathway members only — never a
 *  percentage or average. Personal groups always read 0/0 (they count nothing). */
export function groupCountLabel(group: KnowledgeGroupView): string {
  return `${group.honed_count}/${group.total_count} honed`
}

/** The header-strip label for one branch: pathway-skill honed count + capstone. */
export function branchCountLabel(branch: KnowledgeBranchView): string {
  const cap = branch.capstone_tier === 'proven' ? 'capstone proven' : 'capstone unproven'
  return `${branch.honed_count}/${branch.total_count} honed · ${cap}`
}

/** Split the map into its pathway branches and the personal "Your additions"
 *  layer. Personal groups (`is_personal`) render after the pathway story and
 *  join no count — the two content classes read as one map without lying about
 *  what counts (06-…). */
export function partitionGroups(view: KnowledgeMapView): {
  pathwayGroups: KnowledgeGroupView[]
  personalGroups: KnowledgeGroupView[]
} {
  return {
    pathwayGroups: view.groups.filter((g) => !g.is_personal),
    personalGroups: view.groups.filter((g) => g.is_personal),
  }
}

/** The pathway groups that hang off one branch (evidence slot), in view order. */
export function branchGroups(view: KnowledgeMapView, slotId: string): KnowledgeGroupView[] {
  return view.groups.filter((g) => !g.is_personal && g.branch === slotId)
}

/** Pathway groups that belong to no evidence-slot branch — `core` groups serving
 *  2+ slots (06-…). They are still pathway content (they count toward the honed
 *  tally); they just render under a shared "Core foundations" section instead of a
 *  single pillar. Defined as "not personal and not under any rendered branch" so no
 *  group is ever dropped, whatever `branch` value the registry emits. */
export function coreGroups(view: KnowledgeMapView): KnowledgeGroupView[] {
  const slotIds = new Set(view.branches.map((b) => b.slot_id))
  return view.groups.filter((g) => !g.is_personal && !slotIds.has(g.branch))
}

/** The nodes belonging to a group, in the group's declared member order. Falls
 *  back to view order for any id not resolved (defensive; the server pairs them). */
export function groupNodes(view: KnowledgeMapView, group: KnowledgeGroupView): KnowledgeNodeView[] {
  const byId = new Map(view.nodes.map((n) => [n.node_id, n]))
  return group.member_node_ids
    .map((id) => byId.get(id))
    .filter((n): n is KnowledgeNodeView => n !== undefined)
}

/** The set-point tiers any node offers. `proven` is never settable (evidence-gated,
 *  the server 409s on it); custom personal nodes have no evidence anchor either, so
 *  they cap at `honed` too. Discovered/training/honed are the honest self-assessment
 *  rungs — the same list for every node kind. */
export const SETTABLE_TIERS: MasteryTier[] = ['discovered', 'training', 'honed']

/** Whether "mark evidence" is available on a node — mirrors the server gate:
 *  a honed, non-personal skill/added-skill node only (capstones and custom nodes
 *  are rejected; a not-yet-honed node has no proof to claim). */
export function canMarkEvidence(node: KnowledgeNodeView): boolean {
  return node.kind === 'skill' && !node.is_personal && node.tier === 'honed'
}
