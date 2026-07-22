import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { KnowledgeMapView, KnowledgeNodeView, MasteryTier } from '../api/types'
import { MASTERY_TIERS } from '../api/types'
import { readSignals } from '../lib/atlas/signals'
import { fmtDate, fmtWhen } from '../lib/datetime'
import {
  SETTABLE_TIERS,
  TIER_MEANING,
  canMarkEvidence,
  tierLabel,
} from '../lib/knowledgeMap'

// The knowledge-map node drawer (KT-D): read a node's blurb / linked study, edit
// its private note, adjust its mastery set-point (the only control that lowers a
// tier), and — on a honed pathway skill — mark evidence (the user-gated path to
// Proven). Custom personal nodes show their description + delete instead of
// taxonomy chips. Every action awaits the server's refreshed map (tiers are
// recomputed there, never here) and hands it back through `onMutate`.

const KIND_EYEBROW: Record<KnowledgeNodeView['kind'], string> = {
  skill: 'Skill node',
  capstone: 'Capstone',
  custom: 'Personal node',
}

function Ladder({ tier }: { tier: MasteryTier }) {
  const at = MASTERY_TIERS.indexOf(tier)
  return (
    <div className="km-ladder">
      {MASTERY_TIERS.map((t, i) => (
        <div key={t} className={`km-st${i < at ? ' done' : ''}${i === at ? ' cur' : ''}`}>
          <span className="km-sdot" />
          <span className="km-sl">{tierLabel(t)}</span>
        </div>
      ))}
    </div>
  )
}

export function NodeDrawer({
  node,
  onMutate,
  onClose,
  busy,
  error,
}: {
  node: KnowledgeNodeView
  /** Run a mutation and adopt its refreshed map. Errors surface via `error`. */
  onMutate: (fn: () => Promise<KnowledgeMapView>) => void
  onClose: () => void
  busy: boolean
  error: string | null
}) {
  const [noteText, setNoteText] = useState(node.note ?? '')

  // Re-seed the editor whenever a different node opens or the stored note changes
  // (e.g. after a save/delete round-trips a fresh view). Keyed on node identity so
  // switching nodes never leaks the previous draft.
  useEffect(() => {
    setNoteText(node.note ?? '')
  }, [node.node_id, node.note])

  const isCapstone = node.kind === 'capstone'
  const isCustom = node.kind === 'custom'
  const noteChanged = noteText.trim() !== (node.note ?? '')

  // Additive atlas signals (SA-A), each read defensively: a null/false signal
  // simply omits its card (the graceful-degradation contract, 02-…).
  const signals = readSignals(node)
  const isProven = node.tier === 'proven'
  const hasEvidence = isProven && (signals.evidenceLabel !== null || signals.evidenceConfirmedAt !== null)
  const hasSessionCounts = signals.sessionsTotal !== null && signals.sessionsDone !== null

  return (
    <>
      <div className="km-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="km-drawer" role="dialog" aria-label={`${node.title} details`}>
        <div className="km-dhead">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="label" style={{ color: 'var(--clay-deep)' }}>
              {KIND_EYEBROW[node.kind]}
            </span>
            <button className="btn btn-quiet sm" type="button" onClick={onClose} aria-label="close">
              ✕
            </button>
          </div>
          <h2 className="t-h3" style={{ marginTop: 6 }}>
            {node.title}
          </h2>
          <Ladder tier={node.tier} />
        </div>

        <div className="km-dbody">
          {(node.blurb || node.description) && (
            <p style={{ fontSize: 13.5, lineHeight: 1.55, margin: 0, color: 'var(--ink-soft)' }}>
              {node.blurb ?? node.description}
            </p>
          )}
          <p className="muted" style={{ fontSize: 12, margin: 0, lineHeight: 1.5 }}>
            <b style={{ color: 'var(--ink-soft)' }}>{tierLabel(node.tier)}</b> — {TIER_MEANING[node.tier]}
            {signals.selfAssessed && <span className="km-satick"> ✓ self-assessed</span>}
          </p>

          {/* Session progress — the same plan/telemetry counts the Today screen
              shows, surfaced onto the node (SA-A). Omitted when absent. */}
          {!isCapstone && (hasSessionCounts || signals.nextSessionAt) && (
            <div className="km-dcounts card soft">
              {hasSessionCounts && (
                <div className="km-cr">
                  <span>Sessions</span>
                  <b>
                    {signals.sessionsDone} of {signals.sessionsTotal} done
                  </b>
                </div>
              )}
              {node.expected_minutes != null && (
                <div className="km-cr">
                  <span>Planned study</span>
                  <b>{node.expected_minutes} min</b>
                </div>
              )}
              {signals.nextSessionAt && (
                <div className="km-cr">
                  <span>Next session</span>
                  <b>{fmtWhen(signals.nextSessionAt)}</b>
                </div>
              )}
            </div>
          )}

          {/* Review shimmer's explanation (08-…: honed on minutes, shaky on
              confidence). Never lowers the tier. */}
          {signals.reviewFlagged && (
            <div className="km-flagcard">
              <b>Revisit?</b> The study minutes are done, but your own check-ins after these
              sessions were shaky. Still honed — just worth a second look.
            </div>
          )}

          {/* Proven evidence anchor (SA-A). Skills carry a confirmed-at time; a
              capstone carries its matched artifact label. Either may be absent. */}
          {hasEvidence && (
            <div>
              <div className="label">Evidence</div>
              <div className="km-evfile" style={{ marginTop: 7 }}>
                <div className="km-fg">✦</div>
                <div>
                  <div className="km-fn">{signals.evidenceLabel ?? 'Confirmed artifact'}</div>
                  <div className="km-fd">
                    ✓{' '}
                    {signals.evidenceConfirmedAt
                      ? `confirmed ${fmtDate(signals.evidenceConfirmedAt)}`
                      : 'confirmed'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {node.kind === 'skill' && node.skill_id && (
            <div>
              <div className="label">Skill</div>
              <div className="km-chipwrap" style={{ marginTop: 7 }}>
                <span className="tag mono">{node.skill_id}</span>
              </div>
            </div>
          )}

          {node.linked_module_ids.length > 0 && (
            <div>
              <div className="label">Linked study</div>
              <div className="km-chipwrap" style={{ marginTop: 7 }}>
                {node.linked_module_ids.map((m) => (
                  <span key={m} className="tag mono">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}

          {isCapstone ? (
            <p className="muted" style={{ fontSize: 12, margin: 0, lineHeight: 1.5 }}>
              This capstone <b>is</b> the pillar. It turns Proven when you confirm the real artifact for
              its evidence slot — there are no study minutes here.
            </p>
          ) : (
            <div className="km-set">
              <div className="label">Adjust mastery</div>
              <div className="row" style={{ gap: 6, marginTop: 7, flexWrap: 'wrap' }}>
                {SETTABLE_TIERS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={`chip sm${t === node.tier ? ' cur' : ''}`}
                    disabled={busy || t === node.tier}
                    onClick={() => onMutate(() => api.setMastery(node.node_id, t))}
                  >
                    {tierLabel(t)}
                  </button>
                ))}
              </div>
              <p className="muted" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.5 }}>
                A set-point is the only control that lowers a tier — down-adjusting re-opens a skill for
                study. Proven is earned with evidence, never set.
              </p>
            </div>
          )}

          <div>
            <div className="label">Private note</div>
            <textarea
              className="textarea"
              style={{ marginTop: 7, minHeight: 72 }}
              aria-label="node note"
              placeholder="Your framing, resources, reminders — never shared, never in a prompt."
              value={noteText}
              maxLength={2000}
              onChange={(e) => setNoteText(e.target.value)}
            />
            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <button
                type="button"
                className="btn btn-soft sm"
                disabled={busy || !noteChanged || noteText.trim().length === 0}
                onClick={() => onMutate(() => api.upsertNote(node.node_id, noteText.trim()))}
              >
                Save note
              </button>
              {node.note && (
                <button
                  type="button"
                  className="btn btn-quiet sm"
                  disabled={busy}
                  onClick={() => onMutate(() => api.deleteNote(node.node_id))}
                >
                  Delete note
                </button>
              )}
            </div>
          </div>

          {canMarkEvidence(node) && (
            <div>
              <button
                type="button"
                className="btn btn-primary sm"
                disabled={busy}
                onClick={() => onMutate(() => api.markNodeEvidence(node.node_id))}
              >
                Mark evidence
              </button>
              <p className="muted" style={{ fontSize: 11.5, marginTop: 8, lineHeight: 1.5 }}>
                Proof needs a real artifact — a repo, doc, talk or demo you can point to. It is the only
                path to Proven.
              </p>
            </div>
          )}

          {isCustom && (
            <button
              type="button"
              className="btn btn-ghost sm"
              disabled={busy}
              onClick={() => onMutate(() => api.deleteCustomNode(node.node_id))}
            >
              Delete node
            </button>
          )}

          {error && <div className="banner-error">{error}</div>}
        </div>
      </aside>
    </>
  )
}
