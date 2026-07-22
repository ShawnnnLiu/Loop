// Star Atlas (SA-C) — pure render helpers for the desktop Observatory. React-free
// and vitest-covered, exactly like layout.ts / bodies.ts: this module owns the
// geometry and the honest status text the SVG glyphs draw declaratively, so the
// components stay logic-free and the math is what's unit-tested.
//
// Normative sources: docs/implementation-plans/knowledge-map-atlas/03-desktop-
// observatory.md (the component decomposition + focus pan) and the reference
// render in docs/design-reference/Loop - Star Atlas.html (statusLine, the trail
// arcs, the radial label placement, panTarget). Every value here is a projection
// of the deterministic map_state fold's output (server tiers + honest counts) plus
// the additive SA-A signals — never an LLM signal, never a score.

import type { KnowledgeMapView, KnowledgeNodeView, MasteryTier } from '../../api/types'
import { MASTERY_TIERS } from '../../api/types'
import { CANONICAL_VIEWPORT } from './layout'
import type { NodeSignals } from './signals'
import { sessionTrail } from './signals'

const HONED_OR_ABOVE = new Set<MasteryTier>(['honed', 'proven'])

/** The honest one-line status of a body — the tooltip meta and the accessible
 *  truth (`01-…`: colour is never the only signal). Deliberately date-free: it
 *  reports counts and flags, not absolute times, so it is stable across locale and
 *  timezone (the drawer localizes the actual timestamps). Degrades gracefully —
 *  a training node with no session data reads "under way", a proven node with no
 *  evidence label still reads "proven". */
export function statusLine(
  node: Pick<KnowledgeNodeView, 'kind' | 'is_personal'>,
  tier: MasteryTier,
  signals: NodeSignals,
): string {
  if (node.kind === 'capstone') {
    if (tier === 'proven') {
      return signals.evidenceLabel
        ? `Capstone ✦ proven · ${signals.evidenceLabel}`
        : 'Capstone ✦ proven'
    }
    return 'Capstone — unproven'
  }

  const pre = node.is_personal ? 'Yours · ' : ''
  switch (tier) {
    case 'proven':
      return `${pre}Proven ✦`
    case 'honed': {
      const flags = [
        signals.reviewFlagged ? 'review-flagged' : null,
        signals.selfAssessed ? 'self-assessed' : null,
      ].filter((f): f is string => f !== null)
      return `${pre}Honed${flags.length ? ` · ${flags.join(' · ')}` : ''}`
    }
    case 'training': {
      const trail = sessionTrail(signals)
      return trail
        ? `${pre}Training · ${trail.done} of ${trail.total} sessions`
        : `${pre}Training · under way`
    }
    default:
      return `${pre}Discovered · on the map, no study yet`
  }
}

/** One arc segment of a training world's orbital session trail. `filled` marks a
 *  session with completed telemetry (drawn in magma); the rest are faint. */
export interface TrailArc {
  d: string
  filled: boolean
}

const TRAIL_R = 20
const TRAIL_GAP = 0.2

/** The orbital session trail as SVG arc paths on an `r=20` ring — one arc per
 *  planned session, the first `done` filled. Takes the `{total, done}` pair a
 *  `BodyDescriptor` already carries (`bodyFor(...).trail`), so a glyph consumes the
 *  descriptor, not raw signals. Mirrors the reference `planetG` trail math;
 *  coordinates rounded to 1 decimal so the output is byte-stable. Returns [] when
 *  the trail is null (the graceful-degradation contract). */
export function trailArcs(trail: { total: number; done: number } | null): TrailArc[] {
  if (trail === null) return []
  const { total, done } = trail
  const span = (Math.PI * 2) / total
  const point = (a: number): [string, string] => [
    (TRAIL_R * Math.cos(a)).toFixed(1),
    (TRAIL_R * Math.sin(a)).toFixed(1),
  ]
  const arcs: TrailArc[] = []
  for (let i = 0; i < total; i++) {
    const a0 = -Math.PI / 2 + i * span + TRAIL_GAP / 2
    const a1 = -Math.PI / 2 + (i + 1) * span - TRAIL_GAP / 2
    const [x0, y0] = point(a0)
    const [x1, y1] = point(a1)
    const large = a1 - a0 > Math.PI ? 1 : 0
    arcs.push({ d: `M${x0} ${y0}A${TRAIL_R} ${TRAIL_R} 0 ${large} 1 ${x1} ${y1}`, filled: i < done })
  }
  return arcs
}

/** Where a world's label sits relative to its orbit position: side planets anchor
 *  outward, top/bottom stack above/below. Mirrors the reference's radial label
 *  placement. Pure function of the orbit angle + the planet centre. */
export interface PlanetLabel {
  anchor: 'start' | 'middle' | 'end'
  x: number
  y: number
}

export function planetLabel(angle: number, x: number, y: number, custom: boolean): PlanetLabel {
  const co = Math.cos(angle)
  const si = Math.sin(angle)
  const off = custom ? 18 : 28
  if (co > 0.35) return { anchor: 'start', x: round1(x + off), y: round1(y + 4) }
  if (co < -0.35) return { anchor: 'end', x: round1(x - off), y: round1(y + 4) }
  return {
    anchor: 'middle',
    x: round1(x),
    y: round1(si < 0 ? y - (custom ? 16 : 26) : y + (custom ? 24 : 32)),
  }
}

/** The focus-glide transform (viewBox units): translate + modest scale so the
 *  focused body sits in the visible half not covered by the drawer, clamped so the
 *  sky never shows its edges. Mirrors the reference `panTarget`. The component
 *  multiplies x/y by the container's px-per-unit so the CSS transform is exact at
 *  any width. Identity when nothing is focused. */
export interface PanTransform {
  x: number
  y: number
  k: number
}

const FOCUS_SCALE = 1.3
/** SVG units the drawer overlays on the right (≈356px drawer over a 1180u sky). */
const DRAWER_COVER = 320

export function panTransform(
  focus: { x: number; y: number } | null,
  drawerOpen: boolean,
): PanTransform {
  if (focus === null) return { x: 0, y: 0, k: 1 }
  const k = FOCUS_SCALE
  const vis = drawerOpen ? CANONICAL_VIEWPORT.w - DRAWER_COVER : CANONICAL_VIEWPORT.w
  const cy = CANONICAL_VIEWPORT.h / 2
  const tx = clamp(vis / 2 - k * focus.x, vis - CANONICAL_VIEWPORT.w * k, 0)
  const ty = clamp(cy - k * focus.y, CANONICAL_VIEWPORT.h - CANONICAL_VIEWPORT.h * k, 0)
  return { x: round1(tx), y: round1(ty), k }
}

/** The honest fraction of pathway worlds at honed-or-above — drives the overall
 *  light-pollution wash (the "flourishing" end state lifts above 0.5). Personal
 *  nodes never count (`06-…`). Zero when there are no pathway worlds. */
export function honedFraction(view: KnowledgeMapView): number {
  const worlds = view.nodes.filter((n) => n.kind !== 'capstone' && !n.is_personal)
  if (worlds.length === 0) return 0
  const honed = worlds.filter((n) => HONED_OR_ABOVE.has(n.tier)).length
  return honed / worlds.length
}

/** The mission-plaque cartouche totals — the accessible textual truth of the whole
 *  map (`01-…`). Honest counts only: worlds honed/proven, capstones proven. */
export interface PlaqueSummary {
  branches: number
  systems: number
  worlds: number
  capstones: number
  honed: number
  proven: number
  capstonesProven: number
}

export function plaqueSummary(view: KnowledgeMapView): PlaqueSummary {
  const worlds = view.nodes.filter((n) => n.kind !== 'capstone' && !n.is_personal)
  const systems = view.groups.filter((g) => !g.is_personal)
  return {
    branches: view.branches.length,
    systems: systems.length,
    worlds: worlds.length,
    capstones: view.branches.length,
    honed: worlds.filter((n) => HONED_OR_ABOVE.has(n.tier)).length,
    proven: worlds.filter((n) => n.tier === 'proven').length,
    capstonesProven: view.branches.filter((b) => b.capstone_tier === 'proven').length,
  }
}

/** True when the map exists but nothing is lit — every world discovered and no
 *  capstone proven. Drives the "Nothing lit yet — first light follows" overlay. */
export function nothingLit(view: KnowledgeMapView): boolean {
  const anyLitNode = view.nodes.some((n) => n.kind !== 'capstone' && n.tier !== 'discovered')
  const anyProvenCapstone = view.branches.some((b) => b.capstone_tier === 'proven')
  return !anyLitNode && !anyProvenCapstone
}

// ——— SA-E ornaments (probe · bloom · instrument edge) ———

/** The world a drifting probe heads for: the earliest scheduled session across
 *  the whole map (`next_session_at`, SA-A). Capstones carry no sessions, so this
 *  is always a world. ISO strings are compared as written (the SA-A field is a
 *  tz-aware start); ties break on node id for determinism. Null when nothing is
 *  scheduled — the probe is then omitted entirely (graceful degradation). */
export function earliestNextSession(
  view: KnowledgeMapView,
): { nodeId: string; at: string } | null {
  let best: { nodeId: string; at: string } | null = null
  for (const n of view.nodes) {
    const at = n.next_session_at
    if (at == null) continue
    if (best === null || at < best.at || (at === best.at && n.node_id < best.nodeId)) {
      best = { nodeId: n.node_id, at }
    }
  }
  return best
}

/** The drifting probe's geometry (canonical viewBox units). It sits `PROBE_STANDOFF`
 *  from its target along the approach vector, nose pointed at the target, its label
 *  clamped inside the rim. `approachFrom` is the owning system's centre when that
 *  system is open (the probe comes in along the orbit radius); null when the system
 *  is collapsed, falling back to the demo's default up-right approach. Mirrors the
 *  reference probe math; pure and byte-stable (rounded). */
export interface ProbeGeometry {
  x: number
  y: number
  /** Nose rotation in degrees, pointing from the probe toward the target. */
  angle: number
  labelX: number
  labelY: number
}

const PROBE_STANDOFF = 85

export function probeGeometry(
  target: { x: number; y: number },
  approachFrom: { x: number; y: number } | null,
): ProbeGeometry {
  let ux = 0.8
  let uy = -0.6
  if (approachFrom) {
    const dx = target.x - approachFrom.x
    const dy = target.y - approachFrom.y
    const len = Math.hypot(dx, dy) || 1
    ux = dx / len
    uy = dy / len
  }
  const x = clamp(target.x + ux * PROBE_STANDOFF, 84, 1096)
  const y = clamp(target.y + uy * PROBE_STANDOFF, 30, 630)
  const angle = (Math.atan2(target.y - y, target.x - x) * 180) / Math.PI
  return {
    x: round1(x),
    y: round1(y),
    angle: round1(angle),
    labelX: round1(clamp(x, 108, 1072)),
    labelY: round1(uy < 0 ? y + 18 : y - 14),
  }
}

/** One engraved tick on the instrument bezel (canonical units). */
export interface TickLine {
  x1: number
  y1: number
  x2: number
  y2: number
}

/** The engraved bezel ticks — top/bottom columns every 40u (longer every third),
 *  short side ticks every 40u. Pure, integer, byte-stable; drawn on the fixed
 *  instrument layer (never zoomed with the sky). Mirrors the reference edge. */
export function bezelTicks(): TickLine[] {
  const ticks: TickLine[] = []
  for (let x = 70; x < 1130; x += 40) {
    const long = x % 120 === 110
    ticks.push({ x1: x, y1: 4, x2: x, y2: long ? 12 : 8 })
    ticks.push({ x1: x, y1: 661, x2: x, y2: long ? 653 : 657 })
  }
  for (let y = 60; y < 620; y += 40) {
    ticks.push({ x1: 4, y1: y, x2: 8, y2: y })
    ticks.push({ x1: 1172, y1: y, x2: 1176, y2: y })
  }
  return ticks
}

/** Node ids whose tier *rose* between two snapshots — the tier-up bloom trigger.
 *  Only strict increases count (a set-point down never blooms); a node absent from
 *  `prev` (just added) does not bloom. Pure over the tier ladder order. */
export function roseNodes(
  prev: ReadonlyMap<string, MasteryTier>,
  nodes: ReadonlyArray<Pick<KnowledgeNodeView, 'node_id' | 'tier'>>,
): string[] {
  const risen: string[] = []
  for (const n of nodes) {
    const before = prev.get(n.node_id)
    if (before === undefined) continue
    if (MASTERY_TIERS.indexOf(n.tier) > MASTERY_TIERS.indexOf(before)) risen.push(n.node_id)
  }
  return risen
}

// ——— small pure helpers ———

function clamp(v: number, lo: number, hi: number): number {
  if (v < lo) return lo
  if (v > hi) return hi
  return v
}

function round1(v: number): number {
  return Math.round(v * 10) / 10
}
