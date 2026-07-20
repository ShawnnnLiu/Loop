// Pure view-model logic for the narrative story layer (NP-E): the character-sheet
// summary, pathway-card fit/slot formatting, and the select consequence preview.
// React-free and unit-tested, same split as lib/intake.ts / lib/fit.ts — every
// number here is a projection of the deterministic narrative kernel's output
// (server-computed card ordering, slot states), never an LLM signal and never a
// score. Card ORDER is fixed server-side (filled_slots desc); the UI renders the
// list as given, so nothing here re-ranks.

import type { EvidenceKind, PathwayCard, PathwaySlotView, SlotState } from '../api/types'

/** One tagged evidence item, the shared shape of a form ExperienceRow and a
 *  stored ExperienceItem — the only fields the character sheet reads. */
export interface TaggedItem {
  kind: EvidenceKind
  theme_tags: string[]
}

/** Human label for a closed evidence kind (the raw enum is lowercase). */
export function kindLabel(kind: EvidenceKind): string {
  return kind.charAt(0).toUpperCase() + kind.slice(1)
}

export interface KindCount {
  kind: EvidenceKind
  count: number
}

/** The "who you are today" strip: how many evidence items of each kind, and the
 *  most-frequent themes. A read-view over confirmed evidence — never a store. */
export interface CharacterSheet {
  total: number
  kindCounts: KindCount[]
  topThemes: string[]
}

/** Build the character-sheet summary. Kind counts follow first-appearance order;
 *  themes rank by frequency (case-insensitively, first spelling wins) then
 *  first-appearance, capped at `maxThemes`. */
export function characterSheet(items: TaggedItem[], maxThemes = 6): CharacterSheet {
  const kindCounts: KindCount[] = []
  const kindIndex = new Map<EvidenceKind, number>()
  const themes = new Map<string, { display: string; count: number; order: number }>()

  items.forEach((item) => {
    const at = kindIndex.get(item.kind)
    if (at === undefined) {
      kindIndex.set(item.kind, kindCounts.length)
      kindCounts.push({ kind: item.kind, count: 1 })
    } else {
      kindCounts[at].count += 1
    }
    for (const raw of item.theme_tags) {
      const tag = raw.trim()
      if (!tag) continue
      const key = tag.toLowerCase()
      const seen = themes.get(key)
      if (seen) seen.count += 1
      else themes.set(key, { display: tag, count: 1, order: themes.size })
    }
  })

  const topThemes = [...themes.values()]
    .sort((a, b) => b.count - a.count || a.order - b.order)
    .slice(0, maxThemes)
    .map((t) => t.display)

  return { total: items.length, kindCounts, topThemes }
}

/** Display label per slot coverage state. `partial` = some-but-not-all required
 *  items (a slot with `min_items > 1`); the plan-linked "in progress" state is a
 *  later increment (it needs the active plan's modules, not just coverage). */
export const SLOT_STATE_LABEL: Record<SlotState, string> = {
  filled: 'Filled',
  partial: 'Partial',
  empty: 'Empty',
}

/** Reuse the existing tag tones: filled → ok (sage), partial → warn, empty →
 *  neutral. Returned as the `tag` class suffix the screens already style. */
export function slotStateTone(state: SlotState): '' | 'ok' | 'warn' {
  if (state === 'filled') return 'ok'
  if (state === 'partial') return 'warn'
  return ''
}

/** The honest "n of m pillars" fit line — never a percentage or score. */
export function fitLine(card: PathwayCard): string {
  return `${card.filled_slots} of ${card.total_slots} pillars`
}

/** A card the user's evidence carries none of — the honest "fresh start" case,
 *  shown, never hidden (choosing an aspirational pathway from zero is legitimate). */
export function isFreshStart(card: PathwayCard): boolean {
  return card.filled_slots === 0
}

/** The pillars a selection would make the plan prioritize: every slot not yet
 *  filled, in template order. Drives the pre-confirm consequence preview. */
export function unfilledSlots(card: PathwayCard): PathwaySlotView[] {
  return card.slots.filter((slot) => slot.state !== 'filled')
}

/** The stored-evidence titles matched to a slot (via the kernel's item indices),
 *  so a filled pillar can name *why* it is filled. Out-of-range indices are
 *  skipped defensively — the kernel only ever emits valid ones. */
export function matchedTitles(slot: PathwaySlotView, experienceTitles: string[]): string[] {
  return slot.matched_item_indices
    .map((i) => experienceTitles[i])
    .filter((title): title is string => typeof title === 'string')
}
