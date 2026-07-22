import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { AddableSkill, KnowledgeGroupView, KnowledgeMapView } from '../api/types'

// Shared inline forms for the knowledge-map create/add actions (KT-D). Extracted
// from KnowledgeMap so the desktop Observatory (SA-C) and the accordion reuse one
// copy — every form runs an existing mutation route verbatim through `onMutate`
// and adopts the refreshed view. No new backend surface.

type Mutate = (fn: () => Promise<KnowledgeMapView>) => void

/** The "Add a skill" picker — the closed add-vocabulary (track slice ∩ placeable −
 *  already-present). Loaded on open; a pick calls add-node (server places it by its
 *  grouping row) and hands back the refreshed map. */
export function AddSkillPicker({ onMutate, busy }: { onMutate: Mutate; busy: boolean }) {
  const [skills, setSkills] = useState<AddableSkill[] | null>(null)
  const [query, setQuery] = useState('')
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    api
      .addVocabulary()
      .then((res) => setSkills(res.skills))
      .catch(() => setLoadError(true))
  }, [])

  const filtered = (skills ?? []).filter((s) =>
    s.title.toLowerCase().includes(query.trim().toLowerCase()),
  )

  return (
    <div className="km-inline-form">
      <div className="label" style={{ color: 'var(--clay-deep)' }}>
        Add a skill
      </div>
      <p className="muted" style={{ fontSize: 11.5, margin: '6px 0 0', lineHeight: 1.5 }}>
        Pick from your track&rsquo;s vocabulary; we place it in the right group. It becomes a
        first-class planning target next time you regenerate.
      </p>
      {loadError ? (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Couldn&rsquo;t load the skill list — try again in a moment.
        </p>
      ) : skills === null ? (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Loading…
        </p>
      ) : skills.length === 0 ? (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Every skill in your track&rsquo;s vocabulary is already on your map.
        </p>
      ) : (
        <>
          <input
            className="input"
            style={{ marginTop: 8 }}
            aria-label="search skills to add"
            placeholder="Search skills…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="km-pick">
            {filtered.map((s) => (
              <button
                key={s.skill_id}
                type="button"
                disabled={busy}
                onClick={() => onMutate(() => api.addKnowledgeNode(s.skill_id))}
              >
                {s.title}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="muted" style={{ fontSize: 12 }}>
                No match.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

/** A small named-entity form (custom group). */
export function CreateForm({
  title,
  withDescription,
  submitLabel,
  busy,
  onSubmit,
}: {
  title: string
  withDescription?: boolean
  submitLabel: string
  busy: boolean
  onSubmit: (name: string, description: string) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  return (
    <div className="km-inline-form">
      <div className="label" style={{ color: 'var(--clay-deep)' }}>
        {title}
      </div>
      <input
        className="input"
        style={{ marginTop: 8 }}
        aria-label={`${title} name`}
        placeholder="Name"
        maxLength={60}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      {withDescription && (
        <input
          className="input"
          style={{ marginTop: 8 }}
          aria-label={`${title} description`}
          placeholder="Description (optional)"
          maxLength={500}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      )}
      <button
        type="button"
        className="btn btn-primary sm"
        style={{ marginTop: 10 }}
        disabled={busy || name.trim().length === 0}
        onClick={() => onSubmit(name.trim(), description.trim())}
      >
        {submitLabel}
      </button>
    </div>
  )
}

/** Create a custom node into a chosen group — the desktop equivalent of the
 *  accordion's inline "+ New node" (the sky has no inline group context, so the
 *  target group is picked here). A custom node lands in any group and counts toward
 *  nothing (`06-…`); the picker offers every group on the map. */
export function CreateNodeForm({
  groups,
  busy,
  onSubmit,
}: {
  groups: KnowledgeGroupView[]
  busy: boolean
  onSubmit: (name: string, groupId: string, description: string) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [groupId, setGroupId] = useState(groups[0]?.group_id ?? '')

  return (
    <div className="km-inline-form">
      <div className="label" style={{ color: 'var(--clay-deep)' }}>
        New node
      </div>
      {groups.length === 0 ? (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Create a group first — a node needs somewhere to live.
        </p>
      ) : (
        <>
          <select
            className="input"
            style={{ marginTop: 8 }}
            aria-label="target group"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
          >
            {groups.map((g) => (
              <option key={g.group_id} value={g.group_id}>
                {g.title}
                {g.is_personal ? ' · yours' : ''}
              </option>
            ))}
          </select>
          <input
            className="input"
            style={{ marginTop: 8 }}
            aria-label="new node name"
            placeholder="Name"
            maxLength={60}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="input"
            style={{ marginTop: 8 }}
            aria-label="new node description"
            placeholder="Description (optional)"
            maxLength={500}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-primary sm"
            style={{ marginTop: 10 }}
            disabled={busy || name.trim().length === 0 || groupId === ''}
            onClick={() => onSubmit(name.trim(), groupId, description.trim())}
          >
            Create node
          </button>
        </>
      )}
    </div>
  )
}
