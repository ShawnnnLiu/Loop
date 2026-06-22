# Design System — Tandem 同舟

The literal source is `reference/app.css` (428 lines: tokens + component classes). Map these onto your codebase's design system rather than porting the CSS verbatim. This file is the index of intent.

## Brand
Deep **ink** + **terracotta/clay**, warm paper backgrounds. Serif display (Newsreader) over a grotesk sans (Hanken). Calm, editorial, trustworthy — the opposite of a hyperactive AI chatbot. The mark is the 同 glyph (ink tile) with a small clay ✓ badge; wordmark "Tandem 同舟". CJK fallbacks (Noto Serif/Sans SC) are loaded because the brand carries Chinese characters.

## Color tokens
```
Ink / text     --ink #16212e   --ink-2 #22303f   --ink-soft #38485a
Muted          --muted #6c7886  --muted-2 #97a0ab
Paper / bg     --paper #fbf8f2  --paper-2 #f4ece0  --paper-3 #ece2d3  --card #ffffff
Clay (primary/AI)  --clay #bd5a39  --clay-deep #9c4527  --clay-soft #f1ddd1  --clay-tint #faeee6
Sage (positive)    --sage #5f7a64  --sage-deep #496650  --sage-soft #e3ebe2
Gold (attention)   --gold #c08a3e  --gold-soft #f6e6cf
Lines          --line #e9e0d2   --line-2 #ddd2bf   --line-3 #cdbfa8
```

### Semantic color usage — keep these meanings consistent
- **Clay** = primary action **and** "AI / proposed / inferred". The AI engine badge, proposed blocks (dashed clay), "AI · please review" chips, inferred-guess flag boxes, primary buttons.
- **Sage** = positive / confirmed / on-track ("✓ read", "Trending up", "on track").
- **Gold** = required-but-missing attention (the "Personal projects · required" box).
- **White card on paper** = accepted / committed (on gcal).
- **Ink fill / strike** = done.

## Type
```
--serif 'Newsreader'      headings, display, numbers (GPA, dates)
--sans  'Hanken Grotesk'  body, UI, labels
--mono  'Spline Sans Mono' meta, timestamps, "Step N/7", token counts, kbd
```
Scale: `.t-display 42` · `.t-h1 32` · `.t-h2 25` · `.t-h3 20` · `.t-h4 17`, all serif, weight 500, tight tracking. `.eyebrow` = 11.5px 700 uppercase clay. `.label`/`.fl` = small uppercase muted field labels.

## Shape & depth
```
--r 16  --r-sm 11  --r-xs 8
--shadow-sm / --shadow / --shadow-lg   (soft, low-spread, ink-tinted)
```
App shell is a fixed **1440×900** grid (`.app`). Cards are white with hairline `--line` borders and `--shadow`. Generous padding (44–64px main columns). Restrained, not glassy.

## State grammar (the most important visual system — see also DATA-MODEL §4)
| State | Class hint | Look |
|---|---|---|
| proposed | `.blk.proposed`, `.rail-item.proposed` | **dashed clay** border, clay tint |
| accepted | `.blk.accepted` | solid white card, on gcal |
| done | `.blk.done` | ink/struck, "logged ✓" sage chip |
| locked | `.blk.locked` | muted, 🔒 / "gcal" chip |
| rest | `.blk.rest` | faint italic |

The legend in the calendar (`proposed / accepted (on gcal) / done`) is the canonical key — surface it to users.

## Component classes (in `app.css`)
- `.tb`, `.brand`, `.tb-nav` — topbar + nav
- `.btn` variants: `btn-primary` (clay), `btn-ink`, `btn-soft`, `btn-ghost`, `btn-quiet`; sizes `sm`/`lg`
- `.chip` variants: `clay`, `clay-solid`, `sage`, `gold`, `on`, `dashed`, `sm`
- `.card`, `.card.soft`, `.card.raise`, `.field`, `.field.flag` (inferred boxes)
- `.engine.det` / `.engine.llm` — the deterministic/AI badge
- `.drop`, `.filecard`, `.fileglyph`, `.guard` (privacy line) — upload + trust
- `.cal-grid`, `.day`, `.blk`, `.rail-item`, `.why`, `.ms-track`, `.ms` — calendar + milestones
- `.dock`, `.approval`, `.bubble` (`agent`/`me`/`tool`), `.composer`, `.slash` — agent
- `.cap` (`.llm`/`.det`) — capability-map cards
- `.kbd`, `.eyebrow`, `.label`, `.divider`, `.legend`, `.sync` — utilities

## Motion (not in the static mocks — add tastefully)
Quiet. Proposed→accepted can pulse the card border from dashed clay to solid; the 60-second undo wants a thin countdown affordance; "synced" pill a subtle breathing dot. Avoid bouncy/AI-flashy motion — it would undercut the calm-trust positioning.
