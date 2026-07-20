import { describe, expect, it } from 'vitest'

import type { PathwayCard, PathwaySlotView } from '../api/types'
import {
  characterSheet,
  fitLine,
  isFreshStart,
  kindLabel,
  matchedTitles,
  slotStateTone,
  unfilledSlots,
} from './story'

function slot(overrides: Partial<PathwaySlotView>): PathwaySlotView {
  return {
    slot_id: 's',
    title: 'Slot',
    state: 'empty',
    matched_item_indices: [],
    ...overrides,
  }
}

function card(overrides: Partial<PathwayCard>): PathwayCard {
  return {
    pathway_id: 'p',
    display_name: 'P',
    spine: 'spine',
    audience_note: 'audience',
    career_track: 'swe',
    filled_slots: 0,
    total_slots: 3,
    slots: [],
    selected: false,
    ...overrides,
  }
}

describe('characterSheet', () => {
  it('counts kinds in first-appearance order and ranks themes by frequency', () => {
    const sheet = characterSheet([
      { kind: 'work', theme_tags: ['Backend-Systems', 'data'] },
      { kind: 'project', theme_tags: ['backend-systems'] },
      { kind: 'work', theme_tags: [] },
    ])
    expect(sheet.total).toBe(3)
    expect(sheet.kindCounts).toEqual([
      { kind: 'work', count: 2 },
      { kind: 'project', count: 1 },
    ])
    // "backend-systems" wins (2) over "data" (1); first spelling is preserved.
    expect(sheet.topThemes).toEqual(['Backend-Systems', 'data'])
  })

  it('is empty for a thin sheet and never fabricates', () => {
    const sheet = characterSheet([])
    expect(sheet).toEqual({ total: 0, kindCounts: [], topThemes: [] })
  })

  it('caps the theme list', () => {
    const items = [
      { kind: 'work' as const, theme_tags: ['a', 'b', 'c', 'd', 'e', 'f', 'g'] },
    ]
    expect(characterSheet(items, 3).topThemes).toEqual(['a', 'b', 'c'])
  })
})

describe('kindLabel', () => {
  it('capitalizes the closed kind enum', () => {
    expect(kindLabel('work')).toBe('Work')
    expect(kindLabel('volunteering')).toBe('Volunteering')
  })
})

describe('card fit + slots', () => {
  it('renders the honest n-of-m pillar line, never a percentage', () => {
    expect(fitLine(card({ filled_slots: 2, total_slots: 6 }))).toBe('2 of 6 pillars')
  })

  it('flags a fresh start at zero filled slots', () => {
    expect(isFreshStart(card({ filled_slots: 0 }))).toBe(true)
    expect(isFreshStart(card({ filled_slots: 1 }))).toBe(false)
  })

  it('previews only the unfilled pillars a selection would prioritize', () => {
    const c = card({
      slots: [
        slot({ slot_id: 'a', state: 'filled' }),
        slot({ slot_id: 'b', state: 'partial' }),
        slot({ slot_id: 'c', state: 'empty' }),
      ],
    })
    expect(unfilledSlots(c).map((s) => s.slot_id)).toEqual(['b', 'c'])
  })

  it('maps coverage state to the existing tag tones', () => {
    expect(slotStateTone('filled')).toBe('ok')
    expect(slotStateTone('partial')).toBe('warn')
    expect(slotStateTone('empty')).toBe('')
  })
})

describe('matchedTitles', () => {
  it('names the evidence behind a filled pillar and skips out-of-range indices', () => {
    const titles = ['Payments service', 'Research assistant']
    expect(matchedTitles(slot({ matched_item_indices: [0] }), titles)).toEqual([
      'Payments service',
    ])
    // A defensive skip — the kernel never emits an out-of-range index.
    expect(matchedTitles(slot({ matched_item_indices: [0, 5] }), titles)).toEqual([
      'Payments service',
    ])
  })
})
