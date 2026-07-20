# Management Consultant — Track Profile

**Proposed enum value:** `management_consultant` · **Wave 4** · Research
grounded 2026-07-19.

## Track decision

Own track — the case-interview canon is one of the most codified prep
processes in any industry: canonical books (*Case in Point*, Victor
Cheng's canon at https://caseinterview.com/interview-process-mbb), a
dominant practice platform (PrepLounge), firm-published loop structure
(McKinsey PEI + interviewer-led case —
https://www.mckinsey.com/careers/interviewing; BCG candidate-led case +
Casey chatbot screen — https://careers.bcg.com/global/en/interview-process;
Bain candidate-led + written cases —
https://www.bain.com/careers/hiring-process/interviewing/), and a **fixed
recruiting calendar** with hard application deadlines. Skill vocabulary is
almost fully disjoint from every engineering track and materially distinct
from `product_manager` (client delivery + case craft vs product
ownership), though the two share an estimation/strategy cluster — shared
entries, many tags.

Like `product_manager`, this track stresses the kind distribution:
`language` is empty, `framework` and `practice` are heavy. The kinds hold.

**Resolver markers:** `"management consultant"`,
`"management consulting"`, `"strategy consultant"`,
`"strategy consulting"`, `"consultant"`? — no: bare `consultant` grabs
"sales consultant", "solutions consultant", "security consultant"; leave
it out. `"consulting"` is the marginal call — it catches "consulting
analyst" and "associate consultant" (Bain's entry title) but also
"security consulting"; if used, it must sit **after** `security_analyst`
and every engineering track in `_TRACK_MARKERS`. Safer additions:
`"associate consultant"`, `"consulting analyst"`, `"mbb"`.
**Precedence hazard:** `"business analyst"` is a data-analyst marker in
`data-analyst.md`, but McKinsey's entry-level title is literally
"Business Analyst" — CONTESTED marker, reconciliation must rule (DA
posting volume likely wins; MC then relies on the consulting-specific
markers).

## Role snapshot

Structures ambiguous business problems for clients and delivers
recommendations as analyses (Excel) and slide decks (PowerPoint). BLS
"management analysts": ~1.1M US jobs (2024), median pay **$101,190**
(May 2024), **+9%** projected growth 2024–34 (much faster than average),
**~98,100 openings/yr**
(https://www.bls.gov/ooh/business-and-financial/management-analysts.htm).
Postings' most-listed hard skills: data analysis, financial modeling,
PowerPoint; Excel fluency (pivot tables, scenario modeling) is assumed
(https://managementconsulted.com/excel-powerpoint/,
https://resumeworded.com/skills-and-keywords/management-consultant-skills).

## Prep-process profile

- **Interview loop:** résumé/cover screen → online assessment (McKinsey
  Solve game; BCG Career Assessment + Casey chatbot; Bain digital
  assessment — https://www.bain.com/careers/hiring-process/digital-assessment/)
  → first round: two back-to-back 45–60 min interviews, each pairing a fit
  segment with a live case (McKinsey: PEI — one story, 10–15 probing
  follow-ups — plus an interviewer-led case; BCG/Bain: candidate-led
  ~30-min cases, occasionally a written case with a short presented
  readout) → final round with partners: deeper fit/PEI plus more cases
  (https://www.mckinsey.com/careers/interviewing,
  https://careers.bcg.com/global/en/case-interview-preparation,
  https://casecoach.com/b/how-different-are-the-interviews-at-mckinsey-bain-and-bcg/).
  The named failure mode: memorized frameworks recited instead of
  hypothesis-driven structuring on the actual problem.
- **Fixed recruiting calendar (scheduling-relevant):** unlike rolling SWE
  hiring, MBB/Big-4 recruiting runs on hard published deadlines — 2026
  undergrad windows cluster June–September (McKinsey Aug 11; BCG
  full-time Jul 7; Bain dual-window Mar 29 / Aug 31), first rounds
  Aug–Oct, finals Sep–Nov, and rolling review fills interview slots 4–6
  weeks before the stated cutoff
  (https://managementconsulted.com/consulting-application-deadlines/,
  https://www.hackingthecaseinterview.com/pages/consulting-recruiting-timeline).
  Prep plans for this track are **deadline-anchored and backward-planned**
  from a fixed date — the planner/scheduler should treat the application
  window as a hard horizon, not an open-ended goal.
- **Anchor resources:** *Case in Point* (Cosentino) — the canonical book;
  caseinterview.com (Victor Cheng) for the hypothesis-driven method;
  PrepLounge for live peer/coach case practice; the 47 firm-published
  practice cases indexed at
  https://igotanoffer.com/blogs/mckinsey-case-interview-blog/case-interview-examples;
  firm official prep pages above. Canon converges on dozens of live
  practice cases (~30–60) before first round, mixed solo/peer/mock.
- **Typical 12-week arc (deadline-anchored):** case anatomy + daily
  mental-math drills → case archetypes (profitability, market entry,
  M&A, pricing, operations) solo with exhibit-reading reps → live peer
  cases + PEI/fit story bank (two stories per firm dimension) →
  firm-specific mocks (interviewer-led vs candidate-led), online-
  assessment practice, written-case rep, final polish before the window.

## Seed skill entries (draft)

### Existing entries — add `management_consultant` tag (~7)

`skill.excel` (defined in `data-analyst.md`; owns `spreadsheets`,
`pivot tables`, `vlookup` — the consulting analysis medium),
`skill.market-sizing` (defined in `product-manager.md`; owns
`market sizing`, `fermi estimation`, `tam sam som` — a core case round;
consider adding alias `guesstimates` there at reconciliation),
`skill.competitive-analysis` (defined in `product-manager.md`; owns
`market research`), `skill.stakeholder-communication` (defined in
`data-analyst.md`; owns `presentation skills`, `stakeholder management`),
`skill.data-storytelling` (defined in `data-analyst.md`),
`skill.unit-economics` (defined in `product-manager.md`; secondary),
`skill.interview-frameworks` (defined in `product-manager.md`; owns
`star method` — fit-round prep; secondary).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.case-interviews` | Case Interviews | `case interview`, `case interviews`, `case prep`, `casing`, `case practice`, `written case` | practice | management_consultant | The central prep artifact; ~30–60 live reps |
| `skill.mental-math` | Mental Math & Case Math | `mental math`, `case math`, `consulting math` | practice | management_consultant | Daily-drill skill; no calculators in cases |
| `skill.structured-problem-solving` | Structured Problem Solving | `structured problem solving`, `hypothesis-driven`, `hypothesis driven approach` | practice | management_consultant | Bare `problem solving` too generic — never an alias |
| `skill.mece` | MECE & Issue Trees | `mece`, `issue tree`, `issue trees`, `problem structuring` | framework | management_consultant | The structuring discipline; `mece` is distinctive despite length |
| `skill.case-frameworks` | Consulting Case Frameworks | `porter's five forces`, `five forces`, `swot`, `bcg matrix`, `value chain analysis`, `4ps` | framework | management_consultant | Prep-specific vocabulary, mirrors PM's `skill.interview-frameworks` pattern |
| `skill.profitability-analysis` | Profitability Analysis | `profitability`, `profitability framework`, `profit tree`, `cost reduction` | concept | management_consultant | Most common case archetype; `profitability` bare is a financial_analyst hazard — see CONTESTED |
| `skill.market-entry` | Market Entry & Growth Strategy | `market entry`, `new market entry`, `growth strategy` | concept | management_consultant | Case archetype; distinct from PM's `go-to-market` (stays on `skill.product-strategy`) |
| `skill.mergers-acquisitions` | M&A & Due Diligence | `mergers and acquisitions`, `m&a`, `due diligence`, `commercial due diligence` | concept | management_consultant, financial_analyst | NEW·shared (ruled 2026-07-19): defined here, financial_analyst add-tags; its `skill.merger-models` keeps only `merger model`/`accretion dilution` mechanics |
| `skill.pricing-strategy` | Pricing Strategy | `pricing strategy`, `pricing` | concept | management_consultant | Case archetype; PM mentions pricing in prose but claims no alias |
| *(folded)* `skill.process-improvement` | Process & Operations Improvement | `process improvement`, `business process improvement`, `lean six sigma`, `six sigma`, `operations improvement`, `operational efficiency` | practice | business_analyst, management_consultant | Ruled 2026-07-19: this profile's operations-improvement mint FOLDED into business-analyst.md's `skill.process-improvement` (defined there; aliases union shown); MC add-tags. Bare `lean` never an alias |
| `skill.exhibit-interpretation` | Exhibit & Chart Interpretation | `exhibit interpretation`, `chart interpretation`, `chart reading` | concept | management_consultant | Case-exhibit reps; avoid generic `data interpretation` |
| `skill.pyramid-principle` | Pyramid Principle | `pyramid principle`, `minto pyramid`, `minto`, `top-down communication` | framework | management_consultant | Minto; storyline skeleton for readouts and decks |
| `skill.slide-writing` | Slide Writing | `slide writing`, `slide design`, `slide decks`, `storylining` | practice | management_consultant | Top posting hard skill with Excel. Ruled 2026-07-19: `powerpoint`/`ppt`/`pitch deck` live on `skill.powerpoint` (financial-analyst.md, NEW·shared FA+MC) — this track add-tags it; `presentation skills` stays on `skill.stakeholder-communication` |
| `skill.fit-interview` | Fit & PEI Interviews | `fit interview`, `personal experience interview`, `pei`, `behavioral stories` | practice | management_consultant | McKinsey PEI: one story, 10–15 follow-ups; `pei` short/noisy — trust long alias |
| `skill.business-strategy` | Business & Corporate Strategy | `business strategy`, `corporate strategy`, `business acumen` | concept | management_consultant | `strategic thinking` stays on PM's `skill.product-strategy` |
| `skill.change-management` | Change Management | `change management`, `organizational change` | concept | management_consultant, hr_specialist | NEW·shared (ruled 2026-07-19): defined here; hr_specialist's identical mint folds in; it_support's `skill.itil` keeps ITIL 4's `change enablement` instead. Bare `transformation` too generic — never an alias |
| `skill.client-management` | Client & Engagement Management | `client management`, `client relationship management`, `client relationships`, `engagement management`, `workstream management`, `client retention`, `book of business`, `policy renewals` | practice | management_consultant, financial_advisor, insurance_agent, real_estate_agent(2°) | NEW·shared (ruled 2026-07-19): defined here; absorbed the insurance (client retention/book of business/policy renewals) and financial-advisor client-relationship mints |

**Optional / deferred** (protect the ≤100 budget; add only with enrichment
or demand evidence): `skill.sql` tag (data-heavy consulting roles),
`skill.tableau`/`skill.data-visualization` tags, `skill.statistics` tag,
Alteryx, think-cell, survey design / expert interviews, a dedicated
online-assessment entry (`solve game`, `casey chatbot` — could later land
as aliases on `skill.case-interviews`), `skill.agile` tag,
financial-modeling tagging (ruled 2026-07-19: `skill.financial-modeling`
homed in financial-analyst.md; MC add-tags on demand), `skill.powerpoint`
tag (financial-analyst.md — replaces the powerpoint aliases this profile
originally drafted on slide-writing).

Total new + existing ≈ 24 — well under the ~55 self-cap and the ~100
prompt budget.

## Alias-collision & FTS5 notes

- Already homed elsewhere — tag, don't mint: `market sizing`/`fermi
  estimation`/`tam sam som` (`skill.market-sizing`, PM), `market research`
  (`skill.competitive-analysis`, PM), `presentation skills`/`stakeholder
  management` (`skill.stakeholder-communication`, DA), `spreadsheets`/
  `pivot tables` (`skill.excel`, DA), `star method`
  (`skill.interview-frameworks`, PM), `strategic thinking`/`go-to-market`
  (`skill.product-strategy`, PM), `unit economics`/`ltv`/`cac`
  (`skill.unit-economics`, PM).
- **CONTESTED (financial_analyst drafted in parallel):** `financial
  modeling`, `valuation`, `dcf` are deliberately NOT claimed here — FP&A
  is their likely home; MC add-tags that entry when it lands. `m&a`,
  `due diligence`, and bare `profitability` are claimed here but flagged:
  if financial_analyst wants them, reconciliation rules; MC's fallbacks
  are the long forms (`commercial due diligence`, `profitability
  framework`, `mergers and acquisitions`).
- **CONTESTED (resolver, not alias):** `business analyst` — DA marker vs
  McKinsey's entry title.
- Short/noisy FTS tokens: `pei`, `ppt`, `swot`, `m&a`, `4ps` — usable,
  but trust the long-alias counts (`personal experience interview`,
  `powerpoint`, `mergers and acquisitions`). `casing` collides with
  ordinary English (pipe/type casing) — advisory only. `pricing`,
  `profitability`, `process improvement` are common corpus prose —
  expect inflated counts, advisory per the general rule.
- Deliberately not aliases (too generic, per the homeless-token policy):
  `problem solving`, `synthesis`, `transformation`, `lean`, `strategy`
  (bare), `consulting` (bare, as an alias), `data interpretation`,
  `frameworks` (bare).

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/business-and-financial/management-analysts.htm | role_taxonomy | BLS OOH anchor; **serves 403 to plain fetchers** — may need manual snapshot |
| https://www.mckinsey.com/careers/interviewing | role_taxonomy | Official PEI + case format; stable |
| https://careers.bcg.com/global/en/interview-process | role_taxonomy | Official BCG loop incl. Casey chatbot screen |
| https://careers.bcg.com/global/en/case-interview-preparation | role_taxonomy | Official BCG case-prep guidance |
| https://www.bain.com/careers/hiring-process/interviewing/ | role_taxonomy | Official Bain loop overview |
| https://www.bain.com/careers/hiring-process/case-interview/ | role_taxonomy | Official Bain case-prep page |
| https://caseinterview.com/interview-process-mbb | role_taxonomy | Victor Cheng canon; hypothesis-driven method; stable for years |
| https://casecoach.com/b/how-different-are-the-interviews-at-mckinsey-bain-and-bcg/ | role_taxonomy | Firm-format differences (interviewer- vs candidate-led) |
| https://managementconsulted.com/mckinsey-pei/ | role_taxonomy | PEI anatomy + dimensions |
| https://managementconsulted.com/excel-powerpoint/ | role_taxonomy | Tool-skill grounding (excel/powerpoint posting language) |
| https://managementconsulted.com/consulting-application-deadlines/ | role_taxonomy | Recruiting-calendar anchor; refreshed yearly — volatile by design |
| https://www.hackingthecaseinterview.com/pages/consulting-recruiting-timeline | role_taxonomy | Loop + timeline stages; yearly refresh |
| https://igotanoffer.com/blogs/mckinsey-case-interview-blog/case-interview-examples | interview_report | Index of 47 firm-published practice cases; igotanoffer **serves 403 to plain fetchers** |
| https://www.preplounge.com/en/blog/consulting/interview/application-deadlines-usa | interview_report | Deadline + experience bank; yearly churn |
| (job boards: linkedin/indeed management-consultant searches) | official_job_posting | Volatile + ToS-restricted; sample per run |

## Enrichment expectations

`case interview`, `powerpoint`, `excel`, `market sizing`, `mece`,
`profitability`, `due diligence` should dominate counts (the last two
partly from ordinary prose — advisory). `circles`-style hits for
`porter's five forces`/`bcg matrix` require the prep-guide pages (they are
in the manifest — that is the point). Zero-support flags likely for
`workstream management`, `exhibit interpretation`, `chart reading`
(corpus prose phrases these variably) — keep them; résumé-resolution
value stands on its own.

## Overlap with existing tracks

vs `product_manager`: the largest overlap — estimation (`market sizing`),
strategy, competitive analysis, unit economics, frameworks-as-prep
culture; divergence is client delivery + case craft vs product ownership.
Shared entries carry both tags. vs `data_analyst`: Excel, storytelling,
stakeholder communication — but no SQL-first screen and no BI-tool core;
overlap is the communication cluster, not the query cluster. vs the
parallel `financial_analyst` draft: the boundary is deal/valuation
mechanics (theirs) vs case strategy + delivery craft (ours) —
`financial modeling`/`valuation`/`dcf` deliberately left to that track,
`m&a`/`due diligence` flagged CONTESTED above. vs every engineering
track: essentially disjoint by design.
