// Star Atlas (SA-C) — the shared SVG <defs> gradient/clip set. SA-B added the sky
// colour tokens to tokens.css but deferred the gradient markup here, because SVG
// gradients cannot live in a stylesheet (see the note in tokens.css). Ported
// verbatim from docs/design-reference/Loop - Star Atlas.html so the chart's fills
// match the visual source of truth exactly. Rendered once by Observatory; every
// glyph references these by id (url(#g-rock), clip-path url(#clip-p14), …).

export function AtlasDefs() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs>
        <radialGradient id="g-sky" cx="50%" cy="38%" r="75%">
          <stop offset="0%" stopColor="#152539" />
          <stop offset="60%" stopColor="#0e1926" />
          <stop offset="100%" stopColor="#0b1420" />
        </radialGradient>
        <radialGradient id="g-vig" cx="50%" cy="45%" r="72%">
          <stop offset="62%" stopColor="#060b12" stopOpacity="0" />
          <stop offset="100%" stopColor="#060b12" stopOpacity=".75" />
        </radialGradient>
        <radialGradient id="g-rock">
          <stop offset="0%" stopColor="#57626f" />
          <stop offset="70%" stopColor="#3c4754" />
          <stop offset="100%" stopColor="#2d3845" />
        </radialGradient>
        <radialGradient id="g-ocean">
          <stop offset="0%" stopColor="#5ab3a7" />
          <stop offset="62%" stopColor="#347a74" />
          <stop offset="100%" stopColor="#24504f" />
        </radialGradient>
        <radialGradient id="g-haze">
          <stop offset="55%" stopColor="#e0764a" stopOpacity="0" />
          <stop offset="82%" stopColor="#e0764a" stopOpacity=".3" />
          <stop offset="100%" stopColor="#e0764a" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-glow">
          <stop offset="0%" stopColor="#e8c07a" stopOpacity=".5" />
          <stop offset="55%" stopColor="#e8c07a" stopOpacity=".16" />
          <stop offset="100%" stopColor="#e8c07a" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-glowc">
          <stop offset="0%" stopColor="#b9c7d6" stopOpacity=".3" />
          <stop offset="100%" stopColor="#b9c7d6" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-lamp">
          <stop offset="0%" stopColor="#e8c07a" stopOpacity=".11" />
          <stop offset="100%" stopColor="#e8c07a" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-corona">
          <stop offset="0%" stopColor="#fff3da" stopOpacity=".95" />
          <stop offset="26%" stopColor="#e8c07a" stopOpacity=".45" />
          <stop offset="100%" stopColor="#e8c07a" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-ember">
          <stop offset="0%" stopColor="#d97a4c" stopOpacity=".5" />
          <stop offset="100%" stopColor="#d97a4c" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-neb-clay">
          <stop offset="0%" stopColor="#bd5a39" stopOpacity=".11" />
          <stop offset="100%" stopColor="#bd5a39" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-neb-teal">
          <stop offset="0%" stopColor="#4d9a92" stopOpacity=".1" />
          <stop offset="100%" stopColor="#4d9a92" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-neb-gold">
          <stop offset="0%" stopColor="#c08a3e" stopOpacity=".1" />
          <stop offset="100%" stopColor="#c08a3e" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-neb-sage">
          <stop offset="0%" stopColor="#5f7a64" stopOpacity=".11" />
          <stop offset="100%" stopColor="#5f7a64" stopOpacity="0" />
        </radialGradient>
        <clipPath id="clip-p14">
          <circle cx="0" cy="0" r="14" />
        </clipPath>
      </defs>
    </svg>
  )
}
