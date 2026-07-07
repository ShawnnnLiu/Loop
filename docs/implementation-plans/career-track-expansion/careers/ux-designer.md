# UX / Product Designer — Track Profile

**Proposed enum value:** `ux_designer` · **Wave 2** · Research grounded
2026-07-06.

## Track decision

Own track, but with a flagged product gap: design prep is
**portfolio-artifact-driven, not question-bank-driven**. The loop stages
are standardized (portfolio review, app critique, whiteboard challenge —
https://igotanoffer.com/blogs/tech/facebook-product-designer-interview),
but most prep time goes into *producing artifacts* (2–3 polished case
studies, per-case decks) rather than studying topics. A plan made only of
"study X" tasks under-models this track — the Strategist/Planner would
need task framing for artifact milestones ("case study #1 drafted", "mock
portfolio review booked"). That is a plan-generation concern, not a
taxonomy concern, and it is why this track is wave 2: land it after the
question-practice-shaped tracks prove the expansion mechanics.

**Why wave 2 also on market grounds:** the 2024–2026 entry-level design
market is scarce and hyper-competitive
(https://uxplaybook.org/articles/ux-designer-job-market-reality-2026) —
weaker product pull than the wave-1 careers.

**Resolver markers:** `"ux designer"`, `"product designer"`,
`"ux/ui"`, `"ui/ux"`, `"ux design"`, `"interaction designer"`,
`"ux researcher"` (judgment call — research is a sibling role; acceptable
approximation).

## Role snapshot

Large established field (est. 2M+ practitioners); BLS projects 23% growth
2021–2031 for the digital-design category; bifurcated market (senior
recovering, entry scarce). Prep infrastructure: NN/g portfolio canon,
Holloway whiteboard-challenge guide, ADPList's 8k+ product-design mentors
doing free portfolio reviews (https://adplist.org/).

## Prep-process profile

- **Interview loop** (Meta archetype): recruiter → portfolio screen →
  portfolio review (walk 1–3 case studies; process, role clarity, impact)
  → **app critique** (live critique of a well-known app) → **whiteboard /
  design challenge** (users → pain points → ideation → flows → sketch →
  success metrics; curveballs) → behavioral
  (https://www.holloway.com/g/land-your-dream-design-job/sections/whiteboard-challenge).
- **Anchor resources:** NN/g portfolio + case-study method
  (https://www.nngroup.com/articles/ux-design-portfolios/); ADPList
  playbook + mock reviews; IxDF case-study guides; company design blogs
  documenting their own loops.
- **Typical arc:** case-study selection + polish (weeks, the bulk) →
  daily app-critique practice → timed whiteboard run-throughs → mock
  portfolio reviews → behavioral stories.

## Seed skill entries (draft)

### Existing entries — add `ux_designer` tag (~2)

`skill.html-css` (secondary — front-end awareness), `skill.agile`
(secondary).

### New entries

Shared NEW entries defined elsewhere that tag `ux_designer`:
`skill.user-research` (product-manager.md), `skill.product-sense`
(data-scientist.md), `skill.stakeholder-communication` (secondary).

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.figma` | Figma | `figma`, `figjam` | tool | ux_designer, product_manager | THE industry-standard tool |
| `skill.design-systems` | Design Systems | `design systems`, `design system`, `component libraries`, `design tokens` | framework | ux_designer | Core posting expectation |
| `skill.interaction-design` | Interaction Design | `interaction design`, `ixd` | concept | ux_designer | Core craft dimension |
| `skill.visual-design` | Visual Design | `visual design`, `ui design`, `visual hierarchy` | concept | ux_designer | "Strong visual sense" posting staple |
| `skill.information-architecture` | Information Architecture | `information architecture`, `ia`, `site mapping` | concept | ux_designer | Classic UX competency |
| `skill.typography` | Typography | `typography`, `type systems` | concept | ux_designer | Probed in app critiques |
| `skill.accessibility` | Accessibility | `accessibility`, `a11y`, `wcag`, `inclusive design` | concept | ux_designer | Growing legal weight; arguably tag swe/mobile too — curation call |
| `skill.usability-heuristics` | Usability Heuristics | `usability heuristics`, `heuristic evaluation`, `nielsen's heuristics` | concept | ux_designer | The evaluative vocabulary of critiques |
| `skill.user-flows` | User Flows & Journey Mapping | `user flows`, `journey mapping`, `customer journey map` | concept | ux_designer, product_manager | NEW·shared; whiteboard staple |
| `skill.design-thinking` | Design Thinking | `design thinking`, `human-centered design`, `hcd`, `double diamond` | framework | ux_designer | Named methodology in postings |
| `skill.wireframing` | Wireframing & Prototyping | `wireframing`, `prototyping`, `wireframes`, `interactive prototypes` | practice | ux_designer | The named deliverables |
| `skill.usability-testing` | Usability Testing | `usability testing`, `user testing`, `moderated testing` | practice | ux_designer | Standard validation practice |
| `skill.ux-case-studies` | Portfolio Case Studies | `ux case study`, `design portfolio`, `portfolio case study` | practice | ux_designer | The primary hiring evidence; bare `portfolio` too generic |
| `skill.app-critique` | App Critique | `app critique`, `design critique` | practice | ux_designer | Its own interview round |
| `skill.whiteboard-challenge` | Whiteboard Design Challenge | `whiteboard challenge`, `design challenge`, `design exercise` | practice | ux_designer | Its own interview round |
| `skill.design-handoff` | Developer Handoff | `design handoff`, `dev handoff`, `design specs` | practice | ux_designer | Collaboration practice in postings |
| `skill.platform-guidelines` | Platform Design Guidelines | `material design`, `human interface guidelines`, `hig` | framework | ux_designer, mobile_engineer | NEW·shared; app-critique vocabulary |
| `skill.personas` | Personas | `personas`, `user personas` | practice | ux_designer | Classic discovery artifact; secondary |
| `skill.research-tools` | Research & Testing Tools | `usertesting`, `maze`, `hotjar`, `dovetail` | tool | ux_designer | Product bundle; secondary; curation call |
| `skill.workshop-facilitation` | Workshop Facilitation | `design sprints`, `workshop facilitation` | practice | ux_designer | Senior-leaning; secondary |

**Optional / deferred:** Sketch (declining), Adobe CC, Framer/ProtoPie,
Miro (generic collaboration), atomic design, AI-assisted design literacy
(`figma ai` — young vocabulary, revisit at enrichment).

## Alias-collision & FTS5 notes

- `figma` is claimed here; the PM track gets it via a shared tag —
  don't mint a PM-side entry.
- `prototyping` may collide conceptually with hardware/eng usage in a
  future track — acceptable for now, noted.
- `ia` is a short token (also "information assurance" in security prose!)
  — treat its counts as unusable; trust `information architecture`.
  Same class: `hig`.
- `design challenge`/`design exercise` are generic-ish; whiteboard counts
  will be optimistic.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://www.nngroup.com/articles/ux-design-portfolios/ | role_taxonomy | Canonical portfolio guidance; NN/g copyright strict — summarize, don't republish |
| https://www.nngroup.com/articles/state-of-ux-2026/ | role_taxonomy | Annual field-state report |
| https://igotanoffer.com/blogs/tech/facebook-product-designer-interview | interview_report | Meta designer loop; anti-bot 403 caveat |
| https://www.holloway.com/g/land-your-dream-design-job/sections/whiteboard-challenge | role_taxonomy | Whiteboard-challenge canon; partially paywalled |
| https://www.design.faire.com/design-blog/desiginganinterviewprocess | company_engineering_blog | A company documenting its own designer loop; small-site link-rot risk |
| https://adplist.substack.com/p/product-design-interview-playbook | role_taxonomy | ADPList interview playbook |
| https://ixdf.org/literature/article/how-to-write-great-case-studies-for-your-ux-design-portfolio | role_taxonomy | IxDF case-study method; some content membership-gated |
| https://www.coursera.org/articles/preparing-for-the-whiteboard-design-challenge | role_taxonomy | Neutral explainer; stable |
| https://medium.com/@westonkarnes/learnings-from-product-design-interviews-7a494d531960 | interview_postmortem | First-person loop postmortem (Google, Dropbox, Lyft) |
| https://www.indeed.com/hire/job-description/ux-designer | official_job_posting | Employer-side JD template — the most *stable* proxy for posting language |
| https://coursecareers.com/blog-posts/core-skills-for-junior-ui-ux-designer | role_taxonomy | Junior skill list; bootcamp source — marketing-adjacent caveat |

## Enrichment expectations

`figma`, `user research`, `prototyping`, `usability testing`,
`design systems`, `accessibility` should dominate. `app critique` and
`whiteboard challenge` only hit via interview-guide pages — expected.
This track is the canary for prose-heavy corpora: design writing names
tools less densely than tech writing, so expect systematically lower
counts than devops/cloud; compare within-track, not across tracks.

## Overlap with existing tracks

vs `swe`: near-zero (html/css awareness only) and a structurally
different evidence model. vs `product_manager`: strongest conceptual
overlap — product sense, user research, journey mapping, figma; PM owns
metrics/strategy, design owns craft + artifacts. vs `mobile_engineer`:
platform guidelines + accessibility shared.
