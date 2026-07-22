// Star Atlas (SA-B) — the deterministic layout engine. React-free, vitest-
// covered. The generated KnowledgeMap carries no coordinates (it is pure
// membership: branches → groups → member nodes, one capstone per slot), so the
// sky must be *computed*, and computed identically on every render. This is a
// force-directed relaxation (README decision 2) made byte-stable by fixed seed
// positions + a fixed iteration count + no randomness (the environment bans
// Math.random / Date.now anyway) + final rounding. Same view → identical output,
// so the sky never jitters between fetches and the reference is snapshot-stable.
//
// Normative source: docs/implementation-plans/knowledge-map-atlas/02-data-
// contract-delta.md, Part A. Region anchors are seeded from the demo's
// composition so the reference pathway echoes the hero; bodies are *relaxed*, so
// exact hero pixels are not reproduced — the deliberate trade for shape-
// adaptivity. Mobile needs no layout (it is a scrolling DOM list, 04-…), so this
// is desktop-only.

import type { KnowledgeMapView } from '../../api/types'

// ——— canonical space ———

/** The demo's viewBox. All math runs here; SVG `viewBox` scales it to any
 *  container, so the layout is resolution-independent. A caller may pass a
 *  viewport of the same 1180:665 aspect to receive coordinates pre-scaled to it
 *  (SA-C renders into exactly that viewBox); the default is the canonical space. */
export const CANONICAL_VIEWPORT = { w: 1180, h: 665 } as const

export interface Viewport {
  w: number
  h: number
}

export interface RegionPlacement {
  /** The branch (evidence slot id, or `core`) this nebula belongs to. */
  branch: string
  cx: number
  cy: number
  rx: number
  ry: number
  /** The `<defs>` gradient id for the nebula fill (`g-neb-clay` / …). */
  grad: string
  labelX: number
  labelY: number
}

export interface CapstonePlacement {
  nodeId: string
  branch: string
  x: number
  y: number
}

export interface SystemPlacement {
  groupId: string
  x: number
  y: number
}

export interface PlanetPlacement {
  nodeId: string
  x: number
  y: number
  /** Orbit angle in radians (label placement key); 0 when the system is closed. */
  angle: number
}

export interface PositionedSky {
  regions: RegionPlacement[]
  capstones: CapstonePlacement[]
  systems: SystemPlacement[]
  /** The "YOUR ADDITIONS" header anchor (scaled), present iff personal groups exist. */
  personalHeader: { x: number; y: number } | null
  /** True when relaxation could not separate the systems and the loud grid
   *  fallback fired (never a scrambled sky, never a silent crop). */
  usedGridFallback: boolean
  /** Members of a group: on a `ORBIT_R` ring when the group is open, collapsed to
   *  the star centre otherwise. Canonical order (member_node_ids). */
  planetsFor(groupId: string): PlanetPlacement[]
}

// ——— tuning constants (fixed → deterministic) ———

const ITER = 300
const K_SPRING = 0.04
const K_REP = 30000
const REP_CUTOFF = 300
const REP_SOFT = 60
const MAX_STEP = 20
const STEP = 1
const SEED_R = 34
const GOLDEN = Math.PI * (3 - Math.sqrt(5)) // golden angle in radians
const ORBIT_R = 64
const RIM_PAD = 40
const SYS_MIN_SEP = 96
/** Second-pass repulsion multiplier when the first relaxation leaves a pair too
 *  close (still deterministic — a fixed extra pass, not an open loop). */
const REP_BOOST = 1.7
const NEB_GRADS = ['g-neb-clay', 'g-neb-teal', 'g-neb-gold', 'g-neb-sage']
const CORE_GRAD = 'g-neb-sage'

// ——— region anchor table (canonical px), keyed by non-core branch count ———

interface Anchor {
  cx: number
  cy: number
  rx: number
  ry: number
}

/** Fixed nebula anchors for `n` non-core branches, distributed across the canvas
 *  and seeded from the demo (n=3 is the hero's llm/int/pub). Anchors are *not*
 *  relaxed — the clusters stay stable and legible; only the bodies inside move. */
function branchAnchors(n: number): Anchor[] {
  switch (n) {
    case 0:
      return []
    case 1:
      return [{ cx: 590, cy: 300, rx: 300, ry: 235 }]
    case 2:
      return [
        { cx: 330, cy: 320, rx: 270, ry: 250 },
        { cx: 850, cy: 320, rx: 270, ry: 250 },
      ]
    case 3:
      // The hero composition (docs/design-reference/Loop - Star Atlas.html REGIONS).
      return [
        { cx: 285, cy: 290, rx: 265, ry: 255 },
        { cx: 900, cy: 285, rx: 235, ry: 240 },
        { cx: 590, cy: 165, rx: 175, ry: 130 },
      ]
    case 4:
      return [
        { cx: 300, cy: 225, rx: 255, ry: 175 },
        { cx: 880, cy: 225, rx: 255, ry: 175 },
        { cx: 300, cy: 470, rx: 255, ry: 165 },
        { cx: 880, cy: 470, rx: 255, ry: 165 },
      ]
    default: {
      // 5–6 (and any over-budget n): a ring around the centre, core in the middle.
      const anchors: Anchor[] = []
      for (let i = 0; i < n; i++) {
        const a = -Math.PI / 2 + (i * 2 * Math.PI) / n
        anchors.push({
          cx: round1(590 + 340 * Math.cos(a)),
          cy: round1(320 + 225 * Math.sin(a)),
          rx: 175,
          ry: 150,
        })
      }
      return anchors
    }
  }
}

/** Where the core nebula sits — lower-centre for sparse maps, dead-centre when
 *  branches ring the edge (n≥5). Core groups seed here. */
function coreAnchor(n: number): Anchor {
  if (n >= 5) return { cx: 590, cy: 332, rx: 150, ry: 130 }
  return { cx: 590, cy: 430, rx: 175, ry: 120 }
}

/** The personal layer's home — bottom-right, beyond the pathway nebulae. */
const PERSONAL_ANCHOR: Anchor = { cx: 960, cy: 578, rx: 120, ry: 90 }
const PERSONAL_HEADER = { x: 960, y: 502 }

// ——— internal sim body ———

interface Body {
  x: number
  y: number
  /** Spring target (a fixed anchor the body relaxes toward). */
  tx: number
  ty: number
}

/** One system's canonical seeding recipe: its group id, its spring anchor, and
 *  its index within that anchor's cluster (drives the golden-angle spiral seed).
 *  Computed once so the first pass and the boosted re-seed are byte-identical. */
interface SystemSeed {
  groupId: string
  anchor: Anchor
  clusterIndex: number
}

interface CapstoneSeed {
  nodeId: string
  branch: string
  headX: number
  headY: number
}

function byGroupId(a: { group_id: string }, b: { group_id: string }): number {
  return a.group_id < b.group_id ? -1 : a.group_id > b.group_id ? 1 : 0
}

/**
 * Position a real KnowledgeMapView into a sky. Pure and deterministic.
 *
 * @param view       the map (membership + tiers + counts).
 * @param viewport   output space; coordinates are scaled from canonical into it
 *                   (default = canonical). Pass the 1180:665-aspect viewBox SA-C
 *                   renders into to avoid distortion.
 * @param openGroups group ids currently expanded — only affects `planetsFor`
 *                   (open → orbit; collapsed → star centre); star/capstone/region
 *                   positions are open-independent, so the sky never reshuffles
 *                   on expand.
 */
export function layoutSky(
  view: KnowledgeMapView,
  viewport: Viewport = CANONICAL_VIEWPORT,
  openGroups: ReadonlySet<string> = new Set(),
): PositionedSky {
  const sx = viewport.w / CANONICAL_VIEWPORT.w
  const sy = viewport.h / CANONICAL_VIEWPORT.h

  // 1. Canonical ordering. Branches keep view.branches order (that is their
  //    canonical order). Groups are sorted by id *within* each partition so the
  //    seed walk depends on ids, not on input array order (order-stability).
  const branches = view.branches
  const slotIds = new Set(branches.map((b) => b.slot_id))
  const pathwayGroups = view.groups.filter((g) => !g.is_personal)
  const personalGroups = [...view.groups.filter((g) => g.is_personal)].sort(byGroupId)
  const coreGroups = [...pathwayGroups.filter((g) => !slotIds.has(g.branch))].sort(byGroupId)

  const n = branches.length
  const bAnchors = branchAnchors(n)
  const cAnchor = coreAnchor(n)

  // 2. Regions (fixed nebulae): one per non-core branch, plus core when it has
  //    groups. Personal has no nebula (just the "YOUR ADDITIONS" header).
  const regions: RegionPlacement[] = branches.map((b, i) => {
    const a = bAnchors[i] ?? cAnchor
    return {
      branch: b.slot_id,
      cx: round1(a.cx * sx),
      cy: round1(a.cy * sy),
      rx: round1(a.rx * sx),
      ry: round1(a.ry * sy),
      grad: NEB_GRADS[i % NEB_GRADS.length],
      labelX: round1(a.cx * sx),
      labelY: round1(Math.max(38, a.cy - a.ry - 22) * sy),
    }
  })
  if (coreGroups.length > 0) {
    regions.push({
      branch: 'core',
      cx: round1(cAnchor.cx * sx),
      cy: round1(cAnchor.cy * sy),
      rx: round1(cAnchor.rx * sx),
      ry: round1(cAnchor.ry * sy),
      grad: CORE_GRAD,
      labelX: round1(cAnchor.cx * sx),
      labelY: round1((cAnchor.cy - cAnchor.ry - 22) * sy),
    })
  }

  // 3. Build the canonical seed recipes (systems then capstones).
  const systemSeeds: SystemSeed[] = []
  branches.forEach((b, i) => {
    const anchor = bAnchors[i] ?? cAnchor
    const groups = [...pathwayGroups.filter((g) => g.branch === b.slot_id)].sort(byGroupId)
    groups.forEach((g, j) => systemSeeds.push({ groupId: g.group_id, anchor, clusterIndex: j }))
  })
  coreGroups.forEach((g, j) => systemSeeds.push({ groupId: g.group_id, anchor: cAnchor, clusterIndex: j }))
  personalGroups.forEach((g, j) =>
    systemSeeds.push({ groupId: g.group_id, anchor: PERSONAL_ANCHOR, clusterIndex: j }),
  )

  const capstoneSeeds: CapstoneSeed[] = branches.map((b, i) => {
    const anchor = bAnchors[i] ?? cAnchor
    return {
      nodeId: b.capstone_node_id,
      branch: b.slot_id,
      headX: anchor.cx,
      headY: clamp(anchor.cy - anchor.ry * 0.62, 60, CANONICAL_VIEWPORT.h - 80),
    }
  })

  // 4. Relax. Systems + capstones repel each other; each springs to its anchor;
  //    everything stays inside the rim. Fixed step, fixed ITER → pure.
  const systemBodies = systemSeeds.map(seedSystemBody)
  const capstoneBodies = capstoneSeeds.map(seedCapstoneBody)
  relax([...systemBodies, ...capstoneBodies], K_REP)

  // Overlap policy: if any two *systems* settle closer than the legibility
  // threshold, re-seed from the same recipes and re-run once with stronger
  // repulsion; if still unmet, fall back to a loud deterministic grid.
  let usedGridFallback = false
  if (!systemsSeparated(systemBodies)) {
    systemSeeds.forEach((seed, i) => Object.assign(systemBodies[i], seedSystemBody(seed)))
    capstoneSeeds.forEach((seed, i) => Object.assign(capstoneBodies[i], seedCapstoneBody(seed)))
    relax([...systemBodies, ...capstoneBodies], K_REP * REP_BOOST)
    if (!systemsSeparated(systemBodies)) {
      gridFallback(systemBodies)
      usedGridFallback = true
      // A loud advisory — never a silent crop or a scrambled sky.
      console.warn(
        `layoutSky: ${systemBodies.length} systems could not be separated to ${SYS_MIN_SEP}px; using grid fallback.`,
      )
    }
  }

  // 5. Emit. Scale canonical → viewport, round for byte-stability.
  const systemCanonical = new Map<string, { x: number; y: number }>()
  systemSeeds.forEach((seed, i) => {
    systemCanonical.set(seed.groupId, { x: systemBodies[i].x, y: systemBodies[i].y })
  })

  const systems: SystemPlacement[] = systemSeeds.map((seed) => {
    const p = systemCanonical.get(seed.groupId)!
    return { groupId: seed.groupId, x: round1(p.x * sx), y: round1(p.y * sy) }
  })

  const capstones: CapstonePlacement[] = capstoneSeeds.map((seed, i) => ({
    nodeId: seed.nodeId,
    branch: seed.branch,
    x: round1(capstoneBodies[i].x * sx),
    y: round1(capstoneBodies[i].y * sy),
  }))

  const membersByGroup = new Map<string, string[]>()
  for (const g of view.groups) membersByGroup.set(g.group_id, g.member_node_ids)

  const planetsFor = (groupId: string): PlanetPlacement[] => {
    const members = membersByGroup.get(groupId) ?? []
    const centre = systemCanonical.get(groupId)
    if (!centre) return []
    if (!openGroups.has(groupId)) {
      // Collapsed: members ride the star centre (they animate out on open).
      return members.map((nodeId) => ({
        nodeId,
        x: round1(centre.x * sx),
        y: round1(centre.y * sy),
        angle: 0,
      }))
    }
    // Open: evenly spaced on the orbit ring. Even spacing is deterministic and
    // provably separates for the ≤8-member budget (2·R·sin(π/8) = 48.9px).
    const count = Math.max(1, members.length)
    return members.map((nodeId, i) => {
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / count
      const x = centre.x + ORBIT_R * Math.cos(angle)
      const y = centre.y + ORBIT_R * Math.sin(angle)
      return { nodeId, x: round1(x * sx), y: round1(y * sy), angle }
    })
  }

  return {
    regions,
    capstones,
    systems,
    personalHeader:
      personalGroups.length > 0
        ? { x: round1(PERSONAL_HEADER.x * sx), y: round1(PERSONAL_HEADER.y * sy) }
        : null,
    usedGridFallback,
    planetsFor,
  }
}

// ——— seeding (pure functions of a recipe) ———

function seedSystemBody(seed: SystemSeed): Body {
  const r = SEED_R * Math.sqrt(seed.clusterIndex + 0.5)
  const a = seed.clusterIndex * GOLDEN
  return {
    x: seed.anchor.cx + r * Math.cos(a),
    y: seed.anchor.cy + r * Math.sin(a),
    tx: seed.anchor.cx,
    ty: seed.anchor.cy,
  }
}

function seedCapstoneBody(seed: CapstoneSeed): Body {
  return { x: seed.headX, y: seed.headY, tx: seed.headX, ty: seed.headY }
}

// ——— the force simulation ———

function relax(bodies: Body[], kRep: number): void {
  const nB = bodies.length
  if (nB === 0) return
  for (let it = 0; it < ITER; it++) {
    const fx = new Array<number>(nB).fill(0)
    const fy = new Array<number>(nB).fill(0)
    // Pairwise repulsion.
    for (let i = 0; i < nB; i++) {
      for (let j = i + 1; j < nB; j++) {
        let dx = bodies[i].x - bodies[j].x
        let dy = bodies[i].y - bodies[j].y
        let d2 = dx * dx + dy * dy
        if (d2 < 0.0001) {
          // Coincident: deterministic index-based nudge so the pair can separate.
          dx = (i - j) * 0.1
          dy = 0.1
          d2 = dx * dx + dy * dy
        }
        const d = Math.sqrt(d2)
        if (d > REP_CUTOFF) continue
        const f = kRep / (d2 + REP_SOFT)
        const ux = dx / d
        const uy = dy / d
        fx[i] += ux * f
        fy[i] += uy * f
        fx[j] -= ux * f
        fy[j] -= uy * f
      }
    }
    // Spring to anchor + integrate + rim containment.
    for (let i = 0; i < nB; i++) {
      fx[i] += K_SPRING * (bodies[i].tx - bodies[i].x)
      fy[i] += K_SPRING * (bodies[i].ty - bodies[i].y)
      bodies[i].x = clamp(
        bodies[i].x + clampMag(fx[i], MAX_STEP) * STEP,
        RIM_PAD,
        CANONICAL_VIEWPORT.w - RIM_PAD,
      )
      bodies[i].y = clamp(
        bodies[i].y + clampMag(fy[i], MAX_STEP) * STEP,
        RIM_PAD,
        CANONICAL_VIEWPORT.h - RIM_PAD,
      )
    }
  }
}

function systemsSeparated(systems: Body[]): boolean {
  for (let i = 0; i < systems.length; i++) {
    for (let j = i + 1; j < systems.length; j++) {
      const dx = systems[i].x - systems[j].x
      const dy = systems[i].y - systems[j].y
      if (Math.sqrt(dx * dx + dy * dy) < SYS_MIN_SEP) return false
    }
  }
  return true
}

/** A loud, deterministic grid of systems across the rim — the last-resort layout
 *  when relaxation cannot separate an over-budget map. Never a scrambled sky. */
function gridFallback(systems: Body[]): void {
  const nB = systems.length
  if (nB === 0) return
  const cols = Math.ceil(Math.sqrt(nB))
  const rows = Math.ceil(nB / cols)
  const usableW = CANONICAL_VIEWPORT.w - 2 * RIM_PAD
  const usableH = CANONICAL_VIEWPORT.h - 2 * RIM_PAD
  for (let i = 0; i < nB; i++) {
    const col = i % cols
    const row = Math.floor(i / cols)
    systems[i].x = RIM_PAD + usableW * ((col + 0.5) / cols)
    systems[i].y = RIM_PAD + usableH * ((row + 0.5) / rows)
  }
}

// ——— pure helpers ———

function clamp(v: number, lo: number, hi: number): number {
  if (v < lo) return lo
  if (v > hi) return hi
  return v
}

function clampMag(v: number, max: number): number {
  if (v > max) return max
  if (v < -max) return -max
  return v
}

function round1(v: number): number {
  return Math.round(v * 10) / 10
}
