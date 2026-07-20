# Business Analyst — Track Profile

**Proposed enum value:** `business_analyst` · **Wave 4** · Research
grounded 2026-07-19.

## Track decision

Own track — prep differs materially from every existing track under the
granularity policy. The codified prep artifact is the IIBA certification
ladder (ECBA → CCBA → CBAP) anchored to the BABOK Guide with published
blueprint weights (https://www.iiba.org/business-analysis-certifications/cbap/),
which no other track shares. The interview loop is
elicitation/case-scenario shaped (analyze a business problem, identify
stakeholders, write requirements) rather than SQL-screen-plus-dashboard
shaped (https://www.hackingthecaseinterview.com/pages/business-analyst-case-interview).
The core vocabulary — BPMN, use cases, BRDs, traceability, UAT, gap
analysis — is mostly disjoint from `data_analyst`'s BI-tool cluster and
from `product_manager`'s product-sense cluster.

**Marker re-homing hazard (must be resolved at implementation time):**
`data-analyst.md` currently claims resolver markers `"business analyst"`,
`"business intelligence"`, and `"bi analyst"` for `data_analyst` — drafted
before this track existed. The ruling this profile proposes:

- `"business analyst"` **re-homes to `business_analyst`** (it is this
  career's literal title; leaving it on `data_analyst` makes the new track
  unreachable for its own name). `data-analyst.md`'s marker list needs a
  coordinated edit in the same increment that adds this track — remove
  `"business analyst"` there; do not let both tuples claim it.
- `"business intelligence"` and `"bi analyst"` **stay with
  `data_analyst`** — BI/dashboard work is DA-shaped (SQL screens,
  visualization rounds), not elicitation-shaped.
- Listed as CONTESTED for the central reconciliation pass; this profile
  does not assume it wins.

**Resolver markers:** `"business analyst"`, `"business analysis"`,
`"business systems analyst"`, `"systems analyst"`,
`"it business analyst"`, `"requirements analyst"`,
`"business process analyst"`, `"process analyst"`,
`"functional analyst"`. Do **not** use `"ba"` — two-letter marker with
false hits ("BA degree", "b.a."); same rejection rationale as PM's `"pm"`
hazard. Precedence: insert **before** `data_analyst` (DA claims bare
`"analytics"`; titles like "business analytics analyst" fall to DA, which
is acceptable — those roles are genuinely analytics-shaped — but the
`business_analyst` tuple must be checked first so "business analyst"
never partial-matches a DA marker). `"systems analyst"` also covers
"business systems analyst" via boundary matching; kept explicit for
clarity. `"product owner"` stays with `product_manager` per its profile —
BA/PO adjacency is real but PO is a delivery role, not a requirements
role. Prefixed titles ("salesforce business analyst", "erp business
analyst", "agile business analyst") resolve via the `"business analyst"`
substring; no extra markers needed.

## Role snapshot

Elicits, documents, and manages requirements; models business processes;
bridges business stakeholders and engineering. Output is artifacts —
BRDs, user stories, process maps, traceability matrices — rather than
dashboards or models. Shares the BLS management-analysts SOC: median pay
$101,190 (May 2024), 9% projected growth 2024–34 (much faster than
average), **~98,100 openings/yr** on average over the decade
(https://www.bls.gov/ooh/business-and-financial/management-analysts.htm).
~25k live US "business analyst" postings on Glassdoor alone
(https://www.glassdoor.com/Job/business-analyst-jobs-SRCH_KO0,16.htm).
Keyword studies put requirements gathering, user stories, SQL, Jira,
Agile/Scrum, stakeholder management, process mapping, and gap analysis in
the overwhelming majority of BA job descriptions
(https://www.resumeadapter.com/blog/business-analyst-resume-keywords).

## Prep-process profile

- **Interview loop:** recruiter screen → BA fundamentals round (SDLC,
  agile vs waterfall, elicitation techniques, artifact definitions:
  BRD vs FRD, use case vs user story) → light SQL/data screen (joins,
  aggregations — "pull your own numbers", not DA-depth window-function
  drills) → case/scenario round: analyze a business problem, identify
  stakeholders, structure requirements, propose an approach, typically
  20–45 minutes talking through the logic
  (https://www.hackingthecaseinterview.com/pages/business-analyst-case-interview)
  → stakeholder-management/behavioral. Interviewers explicitly probe
  SDLC, Agile/Scrum, and elicitation-technique mastery
  (https://www.kore1.com/business-analyst-interview-questions/,
  https://www.datacamp.com/blog/business-analyst-interview-questions-and-answers).
- **Exam pipeline (the codified prep artifact):** IIBA ladder anchored to
  the BABOK Guide's six knowledge areas (Planning & Monitoring,
  Elicitation & Collaboration, Requirements Life Cycle Management,
  Strategy Analysis, Requirements Analysis & Design Definition, Solution
  Evaluation). **ECBA**: no experience requirement, 21 professional-
  development hours, 50 questions/1 hr — the entry-achievable credential
  (https://www.iiba.org/business-analysis-certifications/certification-faq/).
  **CCBA**: 3,750 BA work hours in 7 years
  (https://www.iiba.org/business-analysis-certifications/ccba/).
  **CBAP**: 7,500 hours in 10 years + 35 PD hours; 120 scenario
  questions/210 min with published blueprint weights — RADD 30%, Strategy
  Analysis 15%, Requirements Life Cycle 15%, Planning & Monitoring 14%,
  Solution Evaluation 14%, Elicitation 12%
  (https://www.iiba.org/business-analysis-certifications/cbap/).
  Alternative: PMI-PBA (Analysis 35% is the heaviest domain —
  https://www.pmi.org/-/media/pmi/documents/public/pdf/certifications/professional-business-analysis-exam-outline.pdf).
- **Credential-prerequisite gate** (wave-3-style concern, worth noting in
  wave 4): CCBA/CBAP hour requirements are *logged work history* the
  taxonomy cannot model as skills. Plans should treat ECBA as the
  achievable prep target for career-switchers; CBAP is a mid-career
  credential, not a study outcome.
- **Typical 12-week arc:** BABOK knowledge areas + elicitation-technique
  vocabulary → process modeling (BPMN, use cases) + documentation
  artifacts (BRD/FRD, acceptance criteria) → SQL + Excel + agile
  ceremonies + Jira fluency → case-round mocks with presented
  recommendations + ECBA blueprint drills.

## Seed skill entries (draft)

Frequency grounding: requirement elicitation, SQL, stakeholder
communication, and BPMN process modeling are named the top BA skills;
Jira/Visio/documentation form a second tier
(https://www.resumeadapter.com/blog/business-analyst-resume-keywords,
https://www.ziprecruiter.com/career/JR-Business-Analyst/Resume-Keywords-and-Skills).

### Existing entries — add `business_analyst` tag (~4)

`skill.sql` (BA screens assume working SQL), `skill.agile` (owns `agile`,
`scrum` — interview staple), `skill.database-design` (secondary — owns
`data modeling`; suggest curation-review alias adds `erd`,
`entity relationship diagram`), `skill.api-design` (secondary — IT-BA
integration/interface requirements).

### New entries

Shared NEW entries defined elsewhere that tag `business_analyst`:
`skill.requirements-gathering` (defined in data-analyst.md as DA-only —
**propose promoting to NEW·shared DA+BA** rather than minting a
duplicate; it owns `requirements gathering`, `business requirements`,
which are top-tier BA posting keywords), `skill.stakeholder-communication`
(data-analyst.md; suggest curation-review alias add
`stakeholder analysis`), `skill.excel` (data-analyst.md), `skill.jira`
(product-manager.md — its own note says "arguably tag data_analyst too";
BA is the stronger case), `skill.prd-writing` (product-manager.md,
secondary — owns `user stories`, see collision notes),
`skill.backlog-management` (product-manager.md, secondary — owns
`kanban`).

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.requirements-elicitation` | Requirements Elicitation | `requirements elicitation`, `elicitation`, `elicitation techniques`, `stakeholder interviews`, `requirements workshops`, `jad` | practice | business_analyst | Named #1 BA skill; BABOK KA (12% of CBAP). Distinct from requirements-*gathering* (the DA-shared entry keeps the generic phrasing; this one owns the technique vocabulary) |
| `skill.process-modeling` | Business Process Modeling | `process modeling`, `process modelling`, `bpmn`, `business process modeling`, `process mapping`, `swimlane diagrams`, `data flow diagrams`, `dfd` | practice | business_analyst | Top-5 posting skill; the case-round whiteboard artifact |
| `skill.use-cases` | Use Cases & UML | `use cases`, `use case diagrams`, `uml`, `uml diagrams`, `activity diagrams` | concept | business_analyst | Artifact-definition round staple ("use case vs user story") |
| `skill.brd-writing` | Requirements Documentation | `brd`, `business requirements document`, `functional requirements`, `non-functional requirements`, `frd`, `functional specification`, `srs` | practice | business_analyst | The BA's PRD-equivalent; `business requirements` itself stays on `skill.requirements-gathering` |
| `skill.requirements-management` | Requirements Traceability | `requirements management`, `requirements traceability`, `traceability matrix`, `rtm` | practice | business_analyst | BABOK RLCM KA (15% of CBAP); PMI-PBA domain |
| `skill.uat` | User Acceptance Testing | `uat`, `user acceptance testing`, `acceptance testing` | practice | business_analyst | Solution-evaluation side of the role; standard posting keyword |
| `skill.gap-analysis` | Gap Analysis | `gap analysis`, `current state analysis`, `as-is to-be` | concept | business_analyst | Top posting keyword; strategy-analysis KA vocabulary |
| `skill.business-case` | Business Case & Feasibility | `business case`, `cost-benefit analysis`, `feasibility analysis`, `roi analysis` | concept | business_analyst | Strategy Analysis KA (15% of CBAP); bare `roi` deliberately excluded (noisy) |
| `skill.process-improvement` | Process & Operations Improvement | `process improvement`, `business process improvement`, `lean six sigma`, `six sigma`, `operations improvement`, `operational efficiency` | practice | business_analyst, management_consultant | NEW·shared (ruled 2026-07-19): absorbed management-consultant.md's operations-improvement mint (aliases union); bare `lean` deliberately excluded (lean startup collision) |
| `skill.sdlc` | SDLC & Delivery Models | `sdlc`, `software development life cycle`, `waterfall` | concept | business_analyst | Explicitly probed in BA fundamentals rounds |
| `skill.babok` | BABOK & BA Certifications | `babok`, `business analysis body of knowledge`, `cbap`, `ccba`, `ecba`, `pmi-pba` | framework | business_analyst | Prep-specific vocabulary, same pattern as PM's `skill.interview-frameworks` — weak-spot inference should reach it even though résumés rarely carry it |
| `skill.visio` | Diagramming Tools | `visio`, `microsoft visio`, `lucidchart` | tool | business_analyst | Second-tier posting keyword; the BPMN delivery vehicle |
| `skill.confluence` | Confluence | `confluence`, `atlassian confluence` | tool | business_analyst, product_manager(2°) | PM profile deferred Confluence to protect its budget; BA is the stronger home (documentation IS the job). Curation call on the PM tag |

**Optional / deferred** (protect the ≤100 budget): Salesforce/CRM-BA and
ERP-BA domain entries, SharePoint, decision tables/DMN, SIPOC,
user-story-mapping (alias risk vs PM's `skill.prd-writing`),
Balsamiq/mockups (vs UX `skill.wireframing` — prefer a UX(2°)-style tag
if demand appears), `skill.power-bi` BA(2°) tag, IIBA-AAC (agile
analysis) as a `skill.babok` alias.

Running total: ~4 existing v1 + ~6 shared-from-other-profiles + 13 new ≈
**23 entries** — comfortably under the ~55 self-cap and the ~100 budget.

## Alias-collision & FTS5 notes

- **CONTESTED — resolver marker, not alias:** `business analyst` (and the
  marker-list edit to data-analyst.md it requires). `business
  intelligence` / `bi analyst` conceded to `data_analyst`; `bi` was
  already flagged noisy there and is not wanted here.
- **CONTESTED:** `user stories` — homed on PM's `skill.prd-writing`. BA
  postings use it heavily; rather than fight the alias, this profile tags
  `skill.prd-writing` with `business_analyst` (secondary). If
  reconciliation prefers a standalone `skill.user-stories` shared PM+BA,
  the alias moves with it — one home either way. Suggested
  curation-review alias add to whichever entry wins: `acceptance
  criteria`.
- `requirements gathering`, `business requirements` stay on
  `skill.requirements-gathering` (data-analyst.md) — proposal is a
  shared-registry promotion (DA+BA), not a re-home. My
  `skill.requirements-elicitation` and `skill.brd-writing` deliberately
  claim disjoint phrasings.
- `agile`, `scrum` → `skill.agile` (v1, per 02-shared-entries ruling);
  `kanban` → PM's `skill.backlog-management`; `data modeling` →
  `skill.database-design` (v1). Tag, don't mint.
- Short/acronym tokens minted here: `uat`, `brd`, `frd`, `srs`, `rtm`,
  `jad`, `uml`, `dfd`, `sdlc`, `bpmn`. All are distinctive
  domain acronyms (unlike `go`/`bi`) so FTS false-positive risk is low,
  but corpus prose spells most of them out — trust the long aliases for
  enrichment counts. `ba` is never an alias or marker (hopelessly
  ambiguous; effectively deliberately homeless).
- `waterfall` is a mild FTS hazard: Excel/finance "waterfall charts" in
  DA-adjacent prose will inflate counts. Résumé resolution is fine
  (skill-mention context); treat its occurrence_count as advisory.
- `as-is to-be` survives normalization (hyphens preserved, no trailing
  period) but is near-zero as an FTS phrase; it exists for résumé
  resolution only.
- `stakeholder interviews` deliberately distinct from UX/PM's
  `user interviews`/`customer interviews` (on `skill.user-research`) —
  different activity, no collision.
- `elicitation` bare is claimed here — no other track plausibly wants it.

## Candidate corpus sources (manifest seeds)

BABOK Guide itself is member-gated and copyrighted — **never ingest the
book**; the IIBA overview/blueprint pages below are the ingestible
surface.

| URL | expected type | note |
|---|---|---|
| https://www.iiba.org/business-analysis-certifications/cbap/ | role_taxonomy | Official CBAP scope + blueprint weights; stable |
| https://www.iiba.org/business-analysis-certifications/ccba/ | role_taxonomy | Official CCBA eligibility/scope; stable |
| https://www.iiba.org/globalassets/certification/ecba/files/ecba-exam-blueprint.pdf | role_taxonomy | Official ECBA exam blueprint PDF; versioned, occasional re-issue |
| https://www.iiba.org/career-resources/a-business-analysis-professionals-foundation-for-success/babok/ | role_taxonomy | BABOK knowledge-area overview page (not the Guide); stable |
| https://www.pmi.org/-/media/pmi/documents/public/pdf/certifications/professional-business-analysis-exam-outline.pdf | role_taxonomy | Official PMI-PBA exam content outline (domain weights); stable PDF |
| https://www.bls.gov/ooh/business-and-financial/management-analysts.htm | role_taxonomy | BLS OOH management analysts; stable; 403s naive fetchers — needs browser UA |
| https://www.bridging-the-gap.com/steps-to-becoming-a-cbap/ | role_taxonomy | Free explainer from the dominant BA-career blog; stable |
| https://businessanalyst.techcanvass.com/business-analyst-skills/ | role_taxonomy | Skills guide, refreshed yearly; commercial blog, free content |
| https://www.resumeadapter.com/blog/business-analyst-resume-keywords | role_taxonomy | Posting-keyword frequency; volatile by design |
| https://www.datacamp.com/blog/business-analyst-interview-questions-and-answers | interview_report | 31-question prep guide; refreshed yearly |
| https://www.indeed.com/hire/interview-questions/business-analyst | interview_report | Employer-side question bank; refreshed |
| https://www.hackingthecaseinterview.com/pages/business-analyst-case-interview | interview_report | Case-round structure guide; stable |
| https://www.kore1.com/business-analyst-interview-questions/ | interview_report | 2026 hiring-playbook loop breakdown |
| (job boards: linkedin/indeed/glassdoor business-analyst searches) | official_job_posting | Volatile + login-gated; sample per run |

## Enrichment expectations

Expect `requirements`, `sql`, `agile`, `stakeholder management`, `jira`,
`excel`, `gap analysis`, `process mapping` to dominate counts. Mid-tier:
`bpmn`, `uat`, `use cases`, `traceability matrix`. Zero-support flags
likely for `jad`, `swimlane diagrams`, `as-is to-be`, `lucidchart` —
keep them; résumé-resolution value stands on its own. `waterfall` counts
will be inflated by chart prose (see FTS notes).

## Overlap with existing tracks

Deliberate seam with `data_analyst`: shares `skill.sql`, `skill.excel`,
`skill.requirements-gathering`, `skill.stakeholder-communication`,
`skill.agile` (~5 entries) but none of the BI/visualization cluster —
dashboards, Tableau, Power BI stay DA-only, which is exactly the boundary
the marker re-homing encodes (BI titles → DA, BA titles → BA). Seam with
`product_manager`: `skill.jira`, `skill.prd-writing`,
`skill.backlog-management`, possibly `skill.confluence` — but PM's
strategy/product-sense/market-sizing cluster is untouched, and the
BA case round (requirements structuring) is a different exercise from the
PM product-sense round. Near-disjoint from `swe` (sql + api-design 2°
only; no DS&A, no system design).
