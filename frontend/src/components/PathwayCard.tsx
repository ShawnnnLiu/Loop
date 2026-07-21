import type { ReactNode } from 'react'

import type { PathwayCard } from '../api/types'
import { SLOT_STATE_LABEL, fitLine, matchedTitles, slotStateTone } from '../lib/story'

// One narrative pathway rendered as a card (NP-E), shared by the onboarding
// "Your story" step, the Progress story panel, and the Tuning change-pathway
// list. Everything structural here is deterministic: the fit line is the
// kernel's honest "n of m pillars" count (never a score), slot states come
// straight from slot_coverage, and the matched item titles name *why* a pillar
// is filled. The optional `fitNote` (NP-F) is LLM prose fetched separately; it
// only decorates the card — the card renders and ranks fine without it.

export function PathwayCardView({
  card,
  experienceTitles = [],
  fitNote,
  onSelect,
  selectLabel = 'Choose this story',
  busy = false,
  confirming = false,
  confirmPrompt,
  confirmLabel = 'Confirm',
  onConfirm,
  onCancel,
}: {
  card: PathwayCard
  /** Stored evidence titles, so filled pillars can name their items. */
  experienceTitles?: string[]
  /** Optional LLM fit note (NP-F): 2-3 sentences on how existing evidence
   *  carries this story's pillars. Display-only; absent until it loads (or if
   *  the call fails). */
  fitNote?: string
  /** When provided, renders a select control; omit for a read-only card. */
  onSelect?: () => void
  selectLabel?: string
  busy?: boolean
  /** When true, the select control is replaced by an inline confirm/cancel
   *  window anchored to this card — so a destructive select (e.g. a plan-
   *  regenerating story switch) is confirmed in view, next to the button the
   *  user pressed, rather than by a banner elsewhere on the page. */
  confirming?: boolean
  confirmPrompt?: ReactNode
  confirmLabel?: string
  onConfirm?: () => void
  onCancel?: () => void
}) {
  return (
    <div
      className="card"
      style={{
        padding: '16px 18px',
        marginTop: 12,
        borderColor: card.selected ? 'var(--sage)' : undefined,
      }}
    >
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
        <div style={{ fontWeight: 700, fontSize: 15.5 }}>{card.display_name}</div>
        <span className={`tag${card.selected ? ' ok' : ''}`} style={{ whiteSpace: 'nowrap' }}>
          {card.selected ? 'Selected · ' : ''}
          {fitLine(card)}
        </span>
      </div>
      <p style={{ fontSize: 13.5, marginTop: 6, lineHeight: 1.5 }}>{card.spine}</p>
      <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>
        For: {card.audience_note}
      </div>

      {fitNote && (
        <p
          style={{
            fontSize: 12.5,
            marginTop: 10,
            lineHeight: 1.5,
            fontStyle: 'italic',
            color: 'var(--ink-soft, inherit)',
          }}
        >
          {fitNote}
        </p>
      )}

      <div className="col" style={{ gap: 6, marginTop: 12 }}>
        {card.slots.map((slot) => {
          const names = matchedTitles(slot, experienceTitles)
          return (
            <div key={slot.slot_id} className="cfg-row" style={{ padding: '6px 0', borderBottom: 'none' }}>
              <div>
                <div className="cl" style={{ fontSize: 13 }}>
                  {slot.title}
                </div>
                {names.length > 0 && (
                  <div className="cs" style={{ fontSize: 11.5 }}>
                    {names.join(' · ')}
                  </div>
                )}
              </div>
              <span className={`tag ${slotStateTone(slot.state)}`.trim()}>
                {SLOT_STATE_LABEL[slot.state]}
              </span>
            </div>
          )
        })}
      </div>

      {onSelect && !confirming && (
        <div className="row" style={{ marginTop: 12 }}>
          <button
            type="button"
            className={`btn ${card.selected ? 'btn-soft' : 'btn-primary'} sm`}
            disabled={busy || card.selected}
            onClick={onSelect}
          >
            {card.selected ? 'Chosen' : selectLabel}
          </button>
        </div>
      )}

      {confirming && (
        <div
          className="card"
          style={{ marginTop: 12, padding: '12px 14px', borderColor: 'var(--clay)' }}
        >
          {confirmPrompt && <div style={{ fontSize: 13 }}>{confirmPrompt}</div>}
          <div className="row" style={{ gap: 8, marginTop: confirmPrompt ? 10 : 0 }}>
            <button
              type="button"
              className="btn btn-primary sm"
              disabled={busy}
              onClick={onConfirm}
            >
              {busy ? 'Switching…' : confirmLabel}
            </button>
            <button
              type="button"
              className="btn btn-quiet sm"
              disabled={busy}
              onClick={onCancel}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
