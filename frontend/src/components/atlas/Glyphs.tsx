// Star Atlas (SA-C) — the celestial-body glyphs. Thin, declarative SVG over the
// pure SA-B descriptors (bodyFor / starFor / beaconFor) and the SA-C render
// helpers (trailArcs) — no logic lives in the JSX, so the components are trivially
// reviewable and the *math* is what's unit-tested. Every path/coordinate is ported
// verbatim from docs/design-reference/Loop - Star Atlas.html (planetG / starG /
// beaconG). Each glyph draws at the local origin (0,0); the caller translates it
// into place. Exported individually so SA-D's MobileSky reuses the same glyphs
// (decision B: a comet is a comet on both platforms).

import type { ReactNode } from 'react'

import type { BodyDescriptor, StarDescriptor } from '../../lib/atlas/bodies'
import { trailArcs } from '../../lib/atlas/render'

/** SA-F — the accessibility wrapper that turns a decorative celestial glyph into a
 *  real, keyboard-operable control. `role="button"` + `tabIndex=0` place it in the
 *  Tab order (document order = reading order, `03-…`); Enter/Space activate it
 *  exactly as a pointer click; the composed accessible name (`bodyAccessibleName` /
 *  `systemAccessibleName`) is what AT announces. The visible focus ring is the CSS
 *  `.rim [role='button']:focus-visible` outline, matching the gold `.selring`
 *  treatment. Keeping the wrapper here (not inline in the JSX) means every chart
 *  body is focusable the same way, and the glyph children stay logic-free. */
export function SvgButton({
  transform,
  className,
  label,
  onActivate,
  onMouseEnter,
  onMouseLeave,
  children,
}: {
  transform?: string
  className?: string
  label: string
  onActivate: () => void
  onMouseEnter?: () => void
  onMouseLeave?: () => void
  children: ReactNode
}) {
  return (
    <g
      transform={transform}
      className={className}
      role="button"
      tabIndex={0}
      aria-label={label}
      onClick={onActivate}
      onKeyDown={(e) => {
        // Enter/Space are the native button activation keys; preventDefault stops
        // Space from scrolling the page (SVG groups have no default activation).
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
          e.preventDefault()
          onActivate()
        }
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </g>
  )
}

/** A world / added-skill node. Barren rock → magma-cracked training → living ocean
 *  → crowned proven, plus the optional session trail, review shimmer, and note
 *  glyph. Comets (the personal layer) delegate to {@link CometGlyph}. */
export function PlanetGlyph({
  body,
  selected,
}: {
  body: BodyDescriptor
  selected: boolean
}) {
  if (body.shape === 'comet') return <CometGlyph body={body} selected={selected} />

  const ocean = body.shape === 'ocean'
  return (
    <>
      {body.emberHalo && <circle className="pulse" r="24" fill="url(#g-ember)" />}
      {body.crowned && (
        <>
          <circle r="26" fill="url(#g-glow)" opacity=".55" />
          <g transform="rotate(-16)">
            <ellipse rx="23" ry="6.5" fill="none" stroke="#d9a959" strokeWidth="1.4" opacity=".55" />
          </g>
        </>
      )}
      <g clipPath="url(#clip-p14)">
        {!ocean ? (
          <>
            <circle r="14" fill="url(#g-rock)" />
            <circle cx="-4" cy="-3" r="3" fill="#2b3644" opacity=".6" />
            <circle cx="5" cy="4" r="2.2" fill="#2b3644" opacity=".55" />
            <circle cx="1" cy="8" r="1.6" fill="#2b3644" opacity=".5" />
            {body.magmaCracks && (
              <g stroke="#e0764a" fill="none">
                <path d="M-12 4 Q-4 7 2 3 T12 6" strokeWidth="2.6" opacity=".25" />
                <path d="M-12 4 Q-4 7 2 3 T12 6" strokeWidth="1.3" />
                <path d="M-8 -8 Q-2 -4 7 -9" strokeWidth=".9" opacity=".8" />
              </g>
            )}
          </>
        ) : (
          <>
            <circle r="14" fill="url(#g-ocean)" />
            <ellipse cx="-4" cy="-5" rx="8" ry="4.6" fill="#6f9a74" transform="rotate(-18 -4 -5)" />
            <ellipse cx="7" cy="6" rx="5.5" ry="3.6" fill="#5f8a68" transform="rotate(14 7 6)" />
            <ellipse cx="-8" cy="7" rx="3" ry="1.8" fill="#6f9a74" opacity=".85" />
            <path d="M-13 -1 Q0 -7 13 -2" stroke="#ffffff" strokeWidth="2" fill="none" opacity=".2" />
            <path d="M-11 6 Q-2 3 9 8" stroke="#ffffff" strokeWidth="1.4" fill="none" opacity=".13" />
            {body.crowned && (
              <>
                <path d="M0 -14 A14 14 0 0 1 0 14 L0 -14 Z" fill="#0b1420" opacity=".38" />
                <g fill="#ffd98f">
                  <circle cx="7" cy="-3" r=".9" />
                  <circle cx="9.5" cy="1.5" r=".8" />
                  <circle cx="6" cy="5" r=".8" />
                  <circle cx="10" cy="-7" r=".7" />
                </g>
              </>
            )}
          </>
        )}
      </g>
      {body.emberHalo && (
        <circle r="16.5" fill="none" stroke="#e0764a" strokeWidth="3" opacity=".14" />
      )}
      {body.discoveredOutline && (
        <circle r="14" fill="none" stroke="rgba(207,218,226,.5)" strokeWidth="1" strokeDasharray="1.5 3" />
      )}
      {body.crowned && (
        <>
          <g transform="rotate(-16)">
            <path d="M-23 0 A23 6.5 0 0 0 23 0" fill="none" stroke="#e8c07a" strokeWidth="1.6" opacity=".9" />
          </g>
          <circle cx="10" cy="10" r="6" fill="#5f7a64" stroke="#0b1420" strokeWidth="1.4" />
          <text x="10" y="12.6" textAnchor="middle" fontSize="7.5" fontWeight="800" fill="#fff">
            ✓
          </text>
        </>
      )}
      {body.trail && (
        <g className="trail">
          {trailArcs(body.trail).map((arc, i) => (
            <path
              key={i}
              d={arc.d}
              fill="none"
              stroke={arc.filled ? '#e0764a' : 'rgba(255,255,255,.15)'}
              strokeWidth="2.2"
              strokeLinecap="round"
            />
          ))}
        </g>
      )}
      {body.reviewShimmer && (
        <circle
          className="shimmer"
          r="17.5"
          fill="none"
          stroke="rgba(232,192,122,.6)"
          strokeWidth="1"
          strokeDasharray="2 4"
        />
      )}
      <circle className="hit" r="22" />
      {body.hasNote && (
        <text x="-19" y="-12" fontSize="9" fill="#cfdae2" opacity=".75">
          ✎
        </text>
      )}
      {selected && <circle className="selring" r="19" />}
    </>
  )
}

/** The personal layer — a chalk-sketched comet with a short dashed tail, never the
 *  rock→ocean ramp, never gilded. Warms only to a faint teal core at honed. */
export function CometGlyph({ body, selected }: { body: BodyDescriptor; selected: boolean }) {
  return (
    <>
      <g opacity=".8">
        <line x1="8" y1="-6" x2="30" y2="-20" stroke="#cfdae2" strokeWidth="1" opacity=".28" />
        <line x1="9" y1="-2" x2="32" y2="-12" stroke="#cfdae2" strokeWidth=".8" opacity=".16" />
        <circle cx="24" cy="-15" r=".9" fill="#cfdae2" opacity=".4" />
        <circle cx="30" cy="-18" r=".7" fill="#cfdae2" opacity=".25" />
      </g>
      <circle
        r="10"
        fill={body.cometWarmed ? 'rgba(79,154,146,.28)' : 'rgba(207,218,226,.05)'}
        stroke="#cfdae2"
        strokeWidth="1.1"
        strokeDasharray="3 3"
        opacity=".85"
      />
      {body.cometWarmed && <circle r="4" fill="rgba(122,190,182,.5)" />}
      <circle className="hit" r="20" />
      {body.hasNote && (
        <text x="-16" y="-11" fontSize="9" fill="#cfdae2" opacity=".75">
          ✎
        </text>
      )}
      {selected && <circle className="selring" r="15" />}
    </>
  )
}

/** A star system — brightness/warmth grow with the honest honed fraction `k`.
 *  The glow radius / core highlight are cosmetic constants over the descriptor's
 *  `k` and `radius` (monotonic-in-k is covered by the SA-B starRadius/warmthColor
 *  tests); everything semantic is decided in `starFor`. */
export function StarGlyph({ star }: { star: StarDescriptor }) {
  const glowR = (12 + 30 * star.k).toFixed(0)
  const highlightR = (star.radius * 0.45).toFixed(1)
  return (
    <>
      {star.k > 0 ? (
        <circle r={glowR} fill="url(#g-glow)" opacity={star.glowOpacity} />
      ) : (
        <circle r="9" fill="url(#g-glowc)" opacity=".6" />
      )}
      {star.emberPulse && <circle className="pulse" r="15" fill="url(#g-ember)" />}
      {star.custom ? (
        <>
          <circle r="4.5" fill="none" stroke="#cfdae2" strokeWidth="1" strokeDasharray="2 2.5" opacity=".7" />
          <circle r="1.6" fill="#cfdae2" opacity=".8" />
        </>
      ) : (
        <>
          {star.crossFlareLength !== null && (
            <g stroke={star.color} strokeWidth="1" opacity={(0.35 + 0.4 * star.k).toFixed(2)}>
              <line y1={-star.crossFlareLength} y2={star.crossFlareLength} />
              <line x1={-star.crossFlareLength} x2={star.crossFlareLength} />
            </g>
          )}
          <circle
            r={star.radius.toFixed(1)}
            fill={star.color}
            className={star.k === 0 ? 'twinkle' : undefined}
            opacity={star.k === 0 ? 0.8 : undefined}
          />
          {star.k > 0 && <circle r={highlightR} fill="#fff8ea" opacity=".9" />}
        </>
      )}
    </>
  )
}

/** A capstone beacon — a caged ember when unproven, a rayed supernova when proven.
 *  Driven by `beaconFor(branch).proven`. */
export function BeaconGlyph({ proven, selected }: { proven: boolean; selected: boolean }) {
  return (
    <>
      {proven ? (
        <>
          <circle r="36" fill="url(#g-corona)" />
          <g className="rays" stroke="#e8c07a" strokeWidth=".9" opacity=".65">
            {Array.from({ length: 8 }, (_, i) => {
              const a = (i * Math.PI) / 4
              const L = i % 2 ? 18 : 27
              return (
                <line
                  key={i}
                  x1={(10 * Math.cos(a)).toFixed(1)}
                  y1={(10 * Math.sin(a)).toFixed(1)}
                  x2={(L * Math.cos(a)).toFixed(1)}
                  y2={(L * Math.sin(a)).toFixed(1)}
                />
              )
            })}
          </g>
          <circle r="7.5" fill="#fff3da" />
          <circle r="3.5" fill="#fffdf7" />
        </>
      ) : (
        <>
          <circle className="pulse" r="14" fill="url(#g-ember)" />
          <g transform="rotate(45)">
            <rect
              x="-11"
              y="-11"
              width="22"
              height="22"
              fill="none"
              stroke="rgba(154,109,47,.7)"
              strokeWidth="1"
              strokeDasharray="2 3"
            />
          </g>
          <circle r="5.5" fill="#4a2e21" />
          <circle r="2.4" fill="#c96f45" opacity=".85" />
        </>
      )}
      <circle className="hit" r="24" />
      {selected && <circle className="selring" r="18" />}
    </>
  )
}
