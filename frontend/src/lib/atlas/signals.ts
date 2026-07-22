// Star Atlas (SA-B) — defensive readers over the additive SA-A view signals.
// The five richer atlas encodings (session trail, next-session probe, proven
// evidence card, review shimmer, self-assessed tick) ride on nullable fields the
// backend computes deterministically (see docs/implementation-plans/
// knowledge-map-atlas/02-data-contract-delta.md, Part B). This module is the one
// place that reads them, and it reads them *defensively*: every field coalesces
// to null/false, so a node whose signal is absent (no scheduled session, no
// evidence yet, a capstone with no session fields) drops that flourish rather
// than fabricating one. That is the graceful-degradation contract made code —
// bodyFor/starFor/beaconFor never depend on any one signal being present.

import type { KnowledgeNodeView } from '../../api/types'

/** The camelCased, always-defined shape the atlas renderers consume. Sourced
 *  from the snake_case SA-A fields on `KnowledgeNodeView`, each defaulted. */
export interface NodeSignals {
  /** Active-plan sessions training this node; null when it has no linked work. */
  sessionsTotal: number | null
  /** Of `sessionsTotal`, how many carry completed telemetry; null in lockstep. */
  sessionsDone: number | null
  /** Earliest scheduled start after now among linked tasks (ISO); null if none. */
  nextSessionAt: string | null
  /** Opaque evidence label behind a proven capstone; null for skills/unproven. */
  evidenceLabel: string | null
  /** When a proven skill's mark-evidence anchor was recorded (ISO); null else. */
  evidenceConfirmedAt: string | null
  /** Honed on raw minutes but not confidence-weighted — the review shimmer. */
  reviewFlagged: boolean
  /** Tier lifted by a user set-point above earned study — the self-assessed tick. */
  selfAssessed: boolean
}

/** The signals a node with no atlas data carries — every flourish absent. Shared
 *  so callers (and tests) have one honest "nothing lit" baseline. */
export const NO_SIGNALS: NodeSignals = {
  sessionsTotal: null,
  sessionsDone: null,
  nextSessionAt: null,
  evidenceLabel: null,
  evidenceConfirmedAt: null,
  reviewFlagged: false,
  selfAssessed: false,
}

/** Read the SA-A signals off a node view, coalescing every field so the result
 *  is total. Accepts a partial node so older/partial payloads (a field not yet
 *  present) degrade to null/false rather than throwing. */
export function readSignals(node: Partial<KnowledgeNodeView>): NodeSignals {
  return {
    sessionsTotal: node.sessions_total ?? null,
    sessionsDone: node.sessions_done ?? null,
    nextSessionAt: node.next_session_at ?? null,
    evidenceLabel: node.evidence_label ?? null,
    evidenceConfirmedAt: node.evidence_confirmed_at ?? null,
    reviewFlagged: node.review_flagged ?? false,
    selfAssessed: node.self_assessed ?? false,
  }
}

/** The orbital session trail is drawn only when *both* counts are present (the
 *  backend fills them in lockstep, but the renderer must not assume it): a
 *  `training` world with no scheduled session yet shows the base planet, no arc.
 *  Returns the {total, done} pair or null. `done` is clamped into [0, total] so a
 *  malformed payload can never render more arcs done than exist. */
export function sessionTrail(signals: NodeSignals): { total: number; done: number } | null {
  const { sessionsTotal, sessionsDone } = signals
  if (sessionsTotal == null || sessionsDone == null) return null
  if (sessionsTotal <= 0) return null
  const done = Math.max(0, Math.min(sessionsDone, sessionsTotal))
  return { total: sessionsTotal, done }
}
