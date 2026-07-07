# Product Manager — Track Profile

**Proposed enum value:** `product_manager` · **Wave 1** · Research
grounded 2026-07-06.

## Track decision

Own track — arguably the most codified prep process of any non-licensed
career: canonical books (*Cracking the PM Interview*, *Decode and
Conquer*), a dominant prep platform (Exponent), and interview round names
standardized industry-wide (product sense, execution, estimation). Almost
no skill overlap with `swe` (no coding rounds at most companies), so the
vocabulary is largely new — but it shares a meaningful analytics cluster
with the data tracks (a/b testing, metrics, funnels, sql).

The first non-engineering track: a useful stressor for the taxonomy's
five `kind`s. `language` is nearly empty and interview *frameworks*
(CIRCLES, STAR) occupy `framework` — the kinds hold up, but distributions
skew hard (see also `../03-wave-3-exam-careers.md`, where the skew is
extreme).

**Resolver markers:** `"product manager"`, `"product management"`,
`"pm"` (judgment call — two-letter marker risks false hits on "pm shift";
boundary matching helps but verify with tests), `"apm"`,
`"product owner"`, `"technical program manager"`? — no: TPM is its own
role family; leave unresolved (→ union fallback) rather than mis-home it.

## Role snapshot

260k+ worldwide PM listings on LinkedIn; open PM roles up ~54% from the
2023 trough (https://www.lennysnewsletter.com/p/state-of-the-product-job-market-in);
Google APM takes ~45 of ~8,000 applicants (<1%). Prep ecosystem is
industrial: books, courses, question banks, mock platforms.

## Prep-process profile

- **Interview loop** (Meta archetype; up to ~6 onsite rounds, mostly with
  PMs — https://igotanoffer.com/en/advice/product-manager-interview-process):
  product sense/design (what to build and why) → analytical
  thinking/execution ("DAU dropped 10%, why?"; metric definition,
  trade-offs) → product strategy (market entry, pricing) → estimation
  (market sizing/Fermi) → behavioral (STAR with metric-probing follow-ups)
  → sometimes technical (conversational) — and, since ~2025, **AI product
  sense** rounds (prototype with a chatbot; "fix a model that's confident
  but wrong" — https://www.tryexponent.com/blog/top-product-manager-interview-questions).
- **Anchor resources:** *Cracking the PM Interview* + *Decode and Conquer*
  (source of CIRCLES/AARM/DIGS); Exponent's canonical 8-week plan (weeks
  1–2 product sense; 3–4 execution; 5 strategy; 6 behavioral; 7 technical
  + AI fluency; 8 mocks; method = one recorded question/day —
  https://www.tryexponent.com/blog/the-ultimate-pm-interview-study-plan);
  Lenny's Newsletter + SVPG/Cagan for ongoing depth.
- **Plan shape note:** PM prep is question-practice-dominated (like SWE)
  rather than artifact-dominated (like design) — the existing scheduling
  model fits without changes.

## Seed skill entries (draft)

Frequency grounding: https://www.jobscan.co/skills/product-manager
(product strategy 50%, user research 41%, agile 35%, communication top
soft skill).

### Existing entries — add `product_manager` tag (~6)

`skill.sql` (pulling your own data is a named must-have), `skill.agile`
(owns `scrum`), `skill.ab-testing`, `skill.api-design` (secondary —
technical-fluency round), `skill.llms` (secondary tag — AI-PM rounds;
puts "LLMs" in the PM weak-spot vocabulary, which is exactly right in
2026), `skill.prompt-engineering` (secondary, same rationale).

### New entries

Shared NEW entries defined elsewhere that tag `product_manager`:
`skill.metric-definition` (owns `north star metric`),
`skill.cohort-funnel-analysis`, `skill.data-storytelling`,
`skill.stakeholder-communication`, `skill.product-sense` (defined in
data-scientist.md), `skill.experiment-design`, `skill.google-analytics`,
`skill.figma` (defined in ux-designer.md, secondary tag).

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.product-strategy` | Product Strategy | `product strategy`, `strategic thinking`, `go-to-market`, `gtm` | concept | product_manager | 50% of postings; own interview round |
| `skill.roadmapping` | Roadmapping | `roadmap`, `roadmapping`, `product roadmap` | practice | product_manager | Top posting keyword |
| `skill.prioritization` | Prioritization Frameworks | `prioritization`, `rice`, `rice scoring`, `trade-off analysis` | concept | product_manager | Named top evaluation axis by hiring managers |
| `skill.market-sizing` | Market Sizing & Estimation | `market sizing`, `fermi estimation`, `tam sam som` | concept | product_manager | Its own interview question type |
| `skill.prd-writing` | PRD & Spec Writing | `prd`, `product requirements document`, `user stories`, `spec writing` | practice | product_manager | Named must-have in hiring blueprints |
| `skill.user-research` | User Research | `user research`, `customer interviews`, `user interviews`, `customer discovery` | practice | product_manager, ux_designer | NEW·shared; 41% of postings |
| `skill.okrs` | OKRs | `okrs`, `okr`, `objectives and key results` | framework | product_manager | Goal-setting framework in postings |
| `skill.competitive-analysis` | Competitive Analysis | `competitive analysis`, `market research` | practice | product_manager | Strategy-round input |
| `skill.jira` | Jira | `jira`, `atlassian jira` | tool | product_manager | Default backlog/sprint tool; arguably tag data_analyst too |
| `skill.product-analytics-tools` | Product Analytics Platforms | `amplitude`, `mixpanel` | tool | product_manager | Fluency correlated with iteration speed; product-bundle curation call |
| `skill.interview-frameworks` | PM Interview Frameworks | `circles`, `circles framework`, `aarrr`, `pirate metrics`, `heart framework`, `star method` | framework | product_manager | Prep-specific vocabulary; a résumé won't carry these but weak-spot inference should — good test of the concept |
| `skill.unit-economics` | Unit Economics | `unit economics`, `ltv`, `cac` | concept | product_manager | Monetization rounds; secondary |
| `skill.jtbd` | Jobs-to-be-Done | `jobs to be done`, `jtbd` | framework | product_manager | Discovery framework; secondary |
| `skill.backlog-management` | Backlog & Sprint Management | `backlog grooming`, `sprint planning`, `kanban` | practice | product_manager | Delivery-side language; secondary |
| `skill.ai-product-management` | AI Product Management | `ai product management`, `ai pm`, `model evals` | concept | product_manager | New dedicated AI rounds; rising |
| `skill.product-launch` | Product Launches | `product launch`, `launch planning` | practice | product_manager | GTM execution; secondary |

**Optional / deferred:** SAFe (enterprise-only), Productboard/Aha!,
Confluence/Notion, Miro/FigJam, experimentation platforms
(optimizely/launchdarkly/statsig — fold into `skill.experiment-design`
aliases if wanted), UX-principles literacy (tag `skill.product-sense`
covers most of it).

## Alias-collision & FTS5 notes

- `scrum` stays on `skill.agile` (v1); `a/b testing` on
  `skill.ab-testing`; `north star metric` on `skill.metric-definition`;
  `product sense`/`product thinking` on `skill.product-sense` (shared
  with data_scientist and ux_designer).
- `pm`, `gtm`, `ltv`, `cac`, `okr` are short tokens — usable but
  interpret with the long-alias counts alongside.
- `star method` risks noise (`star` prose); the two-word form is required,
  bare `star` must never be an alias.
- `rice` is a food — the framework sense dominates in this corpus class,
  but treat counts as advisory (the general rule anyway).

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://igotanoffer.com/en/advice/product-manager-interview-process | role_taxonomy | Definitive loop-stage taxonomy; **serves 403 to plain fetchers** — anti-bot; may need manual snapshot |
| https://igotanoffer.com/blogs/product-manager/product-manager-interview-questions | role_taxonomy | The "8 question types" taxonomy |
| https://www.tryexponent.com/blog/the-ultimate-pm-interview-study-plan | role_taxonomy | Canonical 8-week plan; refreshed yearly |
| https://www.tryexponent.com/blog/top-product-manager-interview-questions | role_taxonomy | Question taxonomy incl. AI rounds |
| https://www.lennysnewsletter.com/p/the-definitive-guide-to-mastering | role_taxonomy | Deep product-sense guide; Substack partial paywall |
| https://igotanoffer.com/blogs/product-manager/facebook-product-sense-interview | interview_report | Meta product-sense anatomy |
| https://medium.com/agileinsider/how-i-prepared-for-facebook-pm-interviews-execution-metrics-8067d942a6d1 | interview_postmortem | First-person execution-round prep; Medium metered |
| https://www.productalliance.com/guides/meta-pm-interview-cheat-sheet | role_taxonomy | Company-specific loop sheet; commercial |
| https://www.svpg.com/articles/ | company_engineering_blog | Cagan canon; all-rights-reserved — link/quote, don't republish |
| https://www.jobscan.co/skills/product-manager | role_taxonomy | Posting-frequency skill data; methodology opaque |
| https://www.crackingthepminterview.com/ | role_taxonomy | Book companion site; ingest site text only |
| (job boards: linkedin PM searches) | official_job_posting | Volatile + ToS-restricted; sample per run |

## Enrichment expectations

`product strategy`, `roadmap`, `a/b testing`, `user research`,
`stakeholder management`, `prioritization` should dominate.
`circles`/`heart framework` will only hit if prep-guide pages are
ingested (they are — that's what the interview_report class is for).
`unit economics` low-support is fine.

## Overlap with existing tracks

vs `swe`: sql + agile + api literacy, nothing else — by design. vs
`data_analyst`/`data_scientist`: the analytics cluster (metrics, funnels,
a/b, storytelling) is genuinely shared — one entry, many tags. vs
`ux_designer`: the largest conceptual overlap (product sense, user
research, journey mapping, figma); divergence is craft-vs-strategy.
Share `concept`/`practice` entries across PM/design rather than
duplicating (one alias, one home).
