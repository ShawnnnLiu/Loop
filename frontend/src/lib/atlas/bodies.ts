// Star Atlas (SA-B) — the tier → celestial-body mapping, as pure descriptors.
// React-free and vitest-covered: this module owns the *math and the choice of
// glyph*, the SVG components (SA-C) are thin renderers over these descriptors.
// It replaces `lib/knowledgeMap.ts::tierTone` (the old fill/ring gilding ramp).
//
// Normative source: docs/implementation-plans/knowledge-map-atlas/01-visual-
// language.md (the tier table, star brightness/warmth math, capstone beacon
// states) and the reference render in docs/design-reference/Loop - Star
// Atlas.html (planetG / starG / beaconG / dustLayer). Every value here is a
// projection of the deterministic map_state fold's output (server tiers + honest
// counts) plus the additive SA-A signals — never an LLM signal, never a score.

import type { KnowledgeBranchView, KnowledgeGroupView, KnowledgeNodeView } from '../../api/types'
import { type NodeSignals, sessionTrail } from './signals'

// ——— worlds (skill / added-skill / custom nodes) ———

/** The planet body a world renders as. `rock` covers discovered + training
 *  (they differ by ornament, not base body); `ocean` covers honed + proven;
 *  `comet` is the personal layer, which never joins the rock→ocean ramp. */
export type PlanetShape = 'rock' | 'ocean' | 'comet'

/** A pure description of one world, driving `PlanetGlyph` (SA-C) declaratively.
 *  Every flourish is a boolean/optional derived from tier + signals, so a world
 *  whose signal is absent simply omits that flourish (degradation contract). */
export interface BodyDescriptor {
  shape: PlanetShape
  /** Dashed chalk outline of a `discovered` (non-personal) world — "on the map,
   *  no study yet." Never on a comet (comets carry their own dashed sketch). */
  discoveredOutline: boolean
  /** `training`: magma cracks across the rock + a soft ember-pulse halo. */
  magmaCracks: boolean
  emberHalo: boolean
  /** `training` orbital trail — one arc per planned session, filled for done —
   *  only when both session counts are present; null otherwise (base planet). */
  trail: { total: number; done: number } | null
  /** `proven`: the tilted ring + `✓` badge + warm glow + lit star-flecked hemi. */
  crowned: boolean
  /** review-flagged (honed-but-shaky): the slow shimmer ring. Never lowers tier. */
  reviewShimmer: boolean
  /** A comet that has warmed to honed shows a faint teal core (never gilds). */
  cometWarmed: boolean
  /** The `✎` note glyph, when the node carries a user note. */
  hasNote: boolean
}

const HONED_OR_ABOVE = new Set(['honed', 'proven'])

/** Map a node + its (server) tier + its signals to a body descriptor. `tier` is
 *  passed explicitly (rather than read off the node) so callers thread the same
 *  authoritative tier the rest of the UI uses; it must equal `node.tier` in
 *  practice but the parameter keeps this function a pure (node, tier, signals)
 *  mapping exactly as `01-…` specifies. */
export function bodyFor(
  node: Pick<KnowledgeNodeView, 'kind' | 'is_personal' | 'note'>,
  tier: KnowledgeNodeView['tier'],
  signals: NodeSignals,
): BodyDescriptor {
  const mastered = HONED_OR_ABOVE.has(tier)
  const hasNote = node.note != null && node.note.trim() !== ''

  // Personal layer — a comet, always. Never rock/ocean, never crowned, never
  // trailed; it caps at honed and joins no count (06-…). It can warm a little.
  if (node.is_personal || node.kind === 'custom') {
    return {
      shape: 'comet',
      discoveredOutline: false,
      magmaCracks: false,
      emberHalo: false,
      trail: null,
      crowned: false,
      reviewShimmer: false,
      cometWarmed: mastered,
      hasNote,
    }
  }

  const training = tier === 'training'
  return {
    shape: mastered ? 'ocean' : 'rock',
    discoveredOutline: tier === 'discovered',
    magmaCracks: training,
    emberHalo: training,
    trail: training ? sessionTrail(signals) : null,
    crowned: tier === 'proven',
    reviewShimmer: signals.reviewFlagged && mastered,
    cometWarmed: false,
    hasNote,
  }
}

// ——— star systems (groups) ———

/** A pure description of one group's star. A group has no tier of its own; its
 *  brightness and warmth are a function of its honest honed fraction `k`. */
export interface StarDescriptor {
  /** Honed fraction `k = honed_count / total_count`, 0 for an empty/personal
   *  group. The single driver of colour, radius, glow and cross-flare. */
  k: number
  /** Personal/custom group: chalk-dashed, never warms, joins no count. */
  custom: boolean
  /** Star fill — cool chalk-white at k=0, warm star-gold at k=1 (custom: chalk). */
  color: string
  /** Core radius, grows with k (custom stars are a fixed small dot). */
  radius: number
  /** Soft glow opacity (uses the warm `g-glow` when lit, cool `g-glowc` at k=0). */
  glowOpacity: number
  /** Cross-flare arm length, present only on a lit non-custom star (k>0). */
  crossFlareLength: number | null
  /** Any member in `training` — the star gains an ember pulse ("active"). */
  emberPulse: boolean
  /** Every member honed — expanding the system draws the one-shot constellation. */
  allHoned: boolean
}

/** Linear interpolate each RGB channel from cool chalk to warm star-gold by `k`,
 *  matching the demo's `mix([176,192,209],[244,206,138],k)`. Rounded per channel
 *  so equal `k` always yields an identical string (determinism). */
export function warmthColor(k: number): string {
  const t = clamp01(k)
  const cool = [176, 192, 209]
  const warm = [244, 206, 138]
  const ch = cool.map((v, i) => Math.round(v + (warm[i] - v) * t))
  return `rgb(${ch[0]},${ch[1]},${ch[2]})`
}

/** Core radius as a function of `k` — `2.6 + 5k` for pathway stars (the demo's
 *  ramp), a fixed 3 for custom stars (they never grow). Monotonic in `k`. */
export function starRadius(k: number, custom: boolean): number {
  if (custom) return 3
  return round1(2.6 + 5 * clamp01(k))
}

export function starFor(
  group: Pick<KnowledgeGroupView, 'honed_count' | 'total_count' | 'is_personal'>,
  members: ReadonlyArray<Pick<KnowledgeNodeView, 'tier'>>,
): StarDescriptor {
  const custom = group.is_personal
  // Personal groups join no count and never warm — k is pinned to 0 regardless
  // of what the payload carries (they should always be 0/0, but this is honest
  // and defensive either way). Pathway groups take the true honed fraction.
  const k = custom || group.total_count <= 0 ? 0 : clamp01(group.honed_count / group.total_count)
  const emberPulse = members.some((m) => m.tier === 'training')
  const allHoned = !custom && group.total_count > 0 && group.honed_count === group.total_count
  return {
    k,
    custom,
    color: custom ? 'var(--chalk)' : warmthColor(k),
    radius: starRadius(k, custom),
    // Lit stars glow warmer and brighter with k (0.3 → 0.9); k=0 uses the cool
    // fixed halo. Matches the demo's `.3 + .6k` on the warm glow.
    glowOpacity: k > 0 ? round2(0.3 + 0.6 * k) : 0.6,
    crossFlareLength: !custom && k > 0 ? round1(9 + 16 * k) : null,
    emberPulse,
    allHoned,
  }
}

// ——— capstone beacons ———

/** A pure description of a capstone beacon: a caged ember when unproven, a rayed
 *  supernova when proven. State is slot coverage, never study minutes (06-…). */
export interface BeaconDescriptor {
  proven: boolean
  label: 'CAPSTONE ✦ PROVEN' | 'CAPSTONE — UNPROVEN'
}

export function beaconFor(
  branch: Pick<KnowledgeBranchView, 'capstone_tier'>,
): BeaconDescriptor {
  const proven = branch.capstone_tier === 'proven'
  return { proven, label: proven ? 'CAPSTONE ✦ PROVEN' : 'CAPSTONE — UNPROVEN' }
}

// ——— seeded star dust ———

/** One dust mote: a faint star placed deterministically by the seeded RNG. */
export interface DustMote {
  x: number
  y: number
  r: number
  /** Warm gold (rare) or cool chalk. */
  gold: boolean
  opacity: number
  /** A subset twinkle; when true, `twinkleDelay` staggers the loop start. */
  twinkle: boolean
  twinkleDelay: number
}

/** Deterministic Lehmer/Park-Miller RNG (the demo's `rng`): pure, seedable, no
 *  `Math.random`, so a given seed always yields the same dust field — the sky is
 *  byte-stable across renders. Returns a generator of floats in [0, 1). */
export function seededRng(seed: number): () => number {
  let s = seed % 2147483647
  if (s <= 0) s += 2147483646
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

/** Build one parallax dust layer deterministically from a seed. Mirrors the
 *  design page's `dustLayer`; the canvas is the canonical 1180×665 viewBox. */
export function dustLayer(
  seed: number,
  count: number,
  rMin: number,
  rSpan: number,
  baseOpacity: number,
): DustMote[] {
  const rand = seededRng(seed)
  const motes: DustMote[] = []
  for (let i = 0; i < count; i++) {
    const x = Math.round(20 + rand() * 1140)
    const y = Math.round(16 + rand() * 632)
    const r = round1(rMin + rand() * rSpan)
    const gold = rand() < 0.12
    const opacity = round2(baseOpacity * (0.5 + rand() * 0.8))
    const twinkle = rand() < 0.3
    const twinkleDelay = round1(rand() * 4)
    motes.push({ x, y, r, gold, opacity, twinkle, twinkleDelay })
  }
  return motes
}

/** The two committed parallax layers (near/far), seeded exactly as the demo. */
export const DUST_NEAR: DustMote[] = dustLayer(7, 95, 0.5, 0.6, 0.3)
export const DUST_FAR: DustMote[] = dustLayer(23, 45, 0.7, 0.9, 0.45)

// ——— small pure helpers ———

function clamp01(v: number): number {
  if (v < 0) return 0
  if (v > 1) return 1
  return v
}

function round1(v: number): number {
  return Math.round(v * 10) / 10
}

function round2(v: number): number {
  return Math.round(v * 100) / 100
}
