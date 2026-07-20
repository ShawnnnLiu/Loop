# Financial Analyst — Track Profile

**Proposed enum value:** `financial_analyst` · **Wave 4** · Research grounded
2026-07-19.

## Track decision

Own track — the first non-tech career in the taxonomy, and its prep canon
is as codified as any tech loop: accounting fundamentals → three-statement
modeling → valuation (DCF/comps/LBO) is the standard technical-interview
sequence taught by the BIWS/M&I and Wall Street Prep guides
(https://mergersandinquisitions.com/investment-banking-interview-questions/,
https://www.wallstreetprep.com/knowledge/build-integrated-3-statement-financial-model/),
and timed Excel modeling tests (2–4 hr take-home or live build-alongs) are
a near-universal screen
(https://www.financial-modeling.com/financial-modeling-interview-questions-guide/).
Skill set is almost fully disjoint from every existing track (no DS&A, no
system design; the only real overlap is the Excel/SQL/BI toolbelt shared
with `data_analyst`).

**Scope boundary vs the CFA path (deliberate position):**
`financial_analyst` covers **interview-and-modeling-drill prep** for
FP&A, corporate-finance, and IB/ER-adjacent analyst roles. The **CFA
charter pipeline is explicitly out of scope** — it is already scoped as a
wave-3 exam career (`../03-wave-3-exam-careers.md`: ~300–400 hrs/level,
sequential level gates, official CFA Institute curriculum), and it needs
the credential-prerequisite contract work that this track does not. When
the CFA career lands it may **share** this track's concept entries
(accounting, valuation, corporate finance) via added track tags, or split
into its own track — that ruling belongs to the wave-3 increment, not
this one. Consequences now: this profile claims no `cfa` resolver marker
and no exam-blueprint aliases (`ethics`, `fixed income` stays soft — see
collisions), so a future CFA track has clean room.

**Resolver markers:** `"financial analyst"`, `"finance analyst"`,
`"fp&a"`, `"fp&a analyst"`, `"financial planning and analysis"`,
`"corporate finance"`, `"investment banking"`,
`"investment banking analyst"`, `"equity research"`,
`"treasury analyst"`. Precedence hazards: do **not** claim
`"quantitative analyst"` or `"quant"` (quant_dev territory);
`"business analyst"` stays with `data_analyst`; bare
`"research analyst"` is deliberately unclaimed (equity vs market vs UX
research — unresolvable). No existing track's markers partially match
these phrases, so insertion order vs the nine live tracks is free; a
future `management_consultant` track must be checked against
`"corporate finance"` at its own landing time.

## Role snapshot

Builds budgets, forecasts, variance analyses, and valuation models to
guide business and investment decisions; the FP&A, corporate-finance,
investment-banking-analyst, and equity-research flavors share one
modeling-centric prep canon. BLS projects **6% growth 2024–34** (faster
than average) and **~29,900 openings/yr**
(https://www.bls.gov/ooh/business-and-financial/financial-analysts.htm).
Postings consistently ask for Excel plus, increasingly, SQL and Power BI
for data pulls and reporting (e.g.
https://www.indeed.com/q-power-bi-financial-analyst-jobs.html); prep
guides frame the loop as accounting + Excel modeling + forecasting cases
+ variance analysis + stakeholder communication
(https://www.interviewpilot.app/interview-guides/financial-analyst).

## Prep-process profile

- **Interview loop:** recruiter screen → technical screen (accounting
  fundamentals: "walk me through the three statements", how a $10
  depreciation change flows through; then valuation: "walk me through a
  DCF", enterprise vs equity value —
  https://mergersandinquisitions.com/investment-banking-interview-questions/,
  https://corporatefinanceinstitute.com/resources/career/walk-me-through-a-dcf/)
  → **Excel modeling test** (2–4 hr take-home model from a data package,
  or a live on-screen build; judged on structure, speed, and input/formula
  conventions —
  https://www.financial-modeling.com/financial-modeling-interview-questions-guide/)
  → FP&A case (budget-vs-actuals variance walkthrough, driver
  decomposition into volume/price/mix/timing —
  https://365financialanalyst.com/career-advice/fp-a-interview-questions/)
  or, IB-side, merger-model/LBO questions and deal discussion →
  behavioral/"your story". M&I recommends **2–3 months** of technical
  prep for candidates without an accounting background.
- **Anchor resources:** CFI **FMVA** certificate — the codified modeling
  curriculum, ~100–120 hrs, published domain weights (financial modeling
  35%, accounting 20%, valuation 15%, FP&A 10%, Excel 8%, data viz 7%,
  qualitative analysis 5% —
  https://corporatefinanceinstitute.com/certifications/financial-modeling-valuation-analyst-fmva-program/);
  AFP **FPAC** (Certified Corporate FP&A Professional) — two-part exam
  (Part I Financial Acumen, Part II Financial Analysis, three domains
  each, spreadsheet-based questions —
  https://fpacert.financialprofessionals.org/exam/specifications);
  free M&I/WSP three-statement and DCF tutorials with downloadable Excel
  files (https://mergersandinquisitions.com/3-statement-model/); WSO
  interview question banks.
- **Typical 12-week arc:** accounting fundamentals + reading the three
  statements → Excel fluency + build the integrated 3-statement model →
  valuation (DCF, comps, and for IB targets LBO/merger mechanics) +
  corporate-finance concepts → timed mock modeling tests + FP&A
  variance/forecast casework + behavioral and deal/market story.

## Seed skill entries (draft)

### Existing entries — add `financial_analyst` tag

v1 entries: `skill.sql`, `skill.python`, `skill.statistics`. Pending
shared entries defined in `data-analyst.md` (wave 1 lands before wave 4):
`skill.excel` (the single most load-bearing tool for this track — its
`pivot tables`/`vlookup` aliases already cover FA screen language),
`skill.power-bi`, `skill.stakeholder-communication`; secondary (2°,
curation call): `skill.dashboards`, `skill.metric-definition`,
`skill.data-storytelling`, `skill.tableau`.

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.financial-modeling` | Financial Modeling | `financial modeling`, `financial modelling`, `three statement model`, `three-statement model`, `3 statement model`, `integrated financial model` | practice | financial_analyst | The track's spine; FMVA weights it 35%. CONTESTED with draft management_consultant — see collisions |
| `skill.accounting-fundamentals` | Accounting Fundamentals | `accounting`, `accounting fundamentals`, `financial accounting`, `accrual accounting`, `gaap`, `us gaap`, `ifrs` | concept | financial_analyst | First-asked technical topic. Bare `accounting` may migrate to a future CPA track — see collisions |
| `skill.financial-statements` | Financial Statement Analysis | `financial statements`, `financial statement analysis`, `income statement`, `balance sheet`, `cash flow statement`, `ratio analysis` | concept | financial_analyst | "Walk me through the three statements" canon |
| `skill.dcf-valuation` | DCF Valuation | `dcf`, `discounted cash flow`, `dcf valuation`, `wacc`, `terminal value`, `free cash flow` | concept | financial_analyst | "Walk me through a DCF" is the signature question |
| `skill.valuation` | Valuation Methods | `valuation`, `comparable company analysis`, `trading comps`, `precedent transactions`, `enterprise value`, `equity value` | concept | financial_analyst | The comps/precedents/DCF triad; EV vs equity value is a staple probe |
| `skill.lbo-modeling` | LBO Modeling | `lbo`, `leveraged buyout`, `lbo model`, `lbo modeling` | concept | financial_analyst | IB/PE-side loops; skippable for pure FP&A targets |
| `skill.merger-models` | Merger Models | `merger model`, `accretion dilution`, `accretion/dilution` | concept | financial_analyst | IB-side mechanics. Ruled 2026-07-19: `m&a`/`mergers and acquisitions`/`due diligence` live on `skill.mergers-acquisitions` (management-consultant.md, NEW·shared MC+FA) — this track add-tags it |
| `skill.corporate-finance` | Corporate Finance Concepts | `corporate finance`, `time value of money`, `npv`, `irr`, `capital budgeting`, `cost of capital` | concept | financial_analyst | NPV/IRR/hurdle-rate literacy |
| `skill.budgeting-forecasting` | Budgeting & Forecasting | `budgeting`, `budgeting and forecasting`, `financial forecasting`, `annual budget`, `rolling forecast`, `budget vs actuals` | practice | financial_analyst | FP&A core. Bare `forecasting` is homed on v1 `skill.time-series` — deliberately NOT claimed |
| `skill.variance-analysis` | Variance Analysis | `variance analysis`, `budget variance`, `flux analysis`, `bridge analysis` | practice | financial_analyst | The FP&A case round: decompose into volume/price/mix/timing drivers |
| `skill.fpa-process` | FP&A Process | `fp&a`, `financial planning and analysis`, `financial planning & analysis`, `long range planning` | concept | financial_analyst | Doubles as resolver-marker vocabulary; FPAC anchor |
| `skill.excel-modeling-tests` | Excel Modeling Tests | `excel modeling test`, `financial modeling test`, `modeling test`, `case study modeling` | practice | financial_analyst | The near-universal screen: timed take-home or live build |
| `skill.scenario-sensitivity` | Scenario & Sensitivity Analysis | `scenario analysis`, `sensitivity analysis`, `scenario planning`, `what-if analysis` | concept | financial_analyst | Data-table drills inside modeling tests |
| `skill.working-capital` | Working Capital & Cash Flow | `working capital`, `cash flow analysis`, `cash flow forecasting`, `13-week cash flow` | concept | financial_analyst | Links the statements; treasury-flavored postings |
| `skill.capital-structure` | Capital Structure | `capital structure`, `debt financing`, `equity financing`, `leverage ratios` | concept | financial_analyst | IB/corp-dev probes |
| `skill.equity-research` | Equity Research & Stock Pitches | `equity research`, `stock pitch`, `investment thesis`, `initiating coverage` | practice | financial_analyst | The ER interview artifact is a pitch, not a model test alone |
| `skill.sec-filings` | SEC Filings & Earnings | `sec filings`, `10-k`, `10-q`, `annual report`, `earnings call` | concept | financial_analyst | Where model inputs come from |
| `skill.management-reporting` | Management Reporting & Close | `management reporting`, `monthly close`, `month-end close`, `board reporting` | practice | financial_analyst | The FP&A operating cadence |
| `skill.erp-systems` | ERP Systems | `erp`, `sap`, `oracle financials`, `netsuite` | tool | financial_analyst | Posting staple; `erp`/`sap` are noisy FTS tokens — see collisions |
| `skill.fpa-planning-tools` | FP&A Planning Platforms | `anaplan`, `hyperion`, `oracle epm`, `workday adaptive planning`, `adaptive insights` | tool | financial_analyst | Named in a large share of FP&A postings |
| `skill.market-data-platforms` | Market Data Platforms | `bloomberg`, `bloomberg terminal`, `capital iq`, `factset`, `refinitiv` | tool | financial_analyst | IB/ER-side toolbelt |
| `skill.powerpoint` | PowerPoint & Deck Building | `powerpoint`, `ppt`, `pitch deck`, `deck building`, `presentation decks` | tool | financial_analyst, management_consultant | NEW·shared (ruled 2026-07-19): defined here; MC's slide-writing entry keeps `slide writing`/`slide decks`/`storylining` and add-tags this |
| `skill.vba` | VBA & Excel Automation | `vba`, `excel macros`, `visual basic for applications` | language | financial_analyst, actuary | NEW·shared (ruled 2026-07-19): defined here; actuary's identical mint folds in; data-analyst.md deferred VBA (DA 2° later on demand). Bare `macros` left homeless |

**Optional / deferred** (protect the budget; add only on enrichment or
user demand): capital-markets literacy entry (`capital markets`, `fixed
income`, `bonds` — deliberately deferred to avoid pre-empting the wave-3
CFA track's blueprint vocabulary), Alteryx, Essbase/`smartview`, Power
Query as its own entry, `financial ratios` split out of
financial-statements, treasury operations, credit analysis.

Draft tally: 22 new + 3 v1 tags + ~3–7 shared tags ≈ **28–32 entries**,
comfortably under the ~55 self-cap and the ~100 prompt budget.

## Alias-collision & FTS5 notes

- `forecasting` → homed on v1 `skill.time-series` (per
  `../02-shared-entries.md` ruling `time series`/`forecasting`). This
  track never claims it; `financial forecasting` and `budgeting and
  forecasting` carry the FP&A meaning. Deliberately **not** tagging
  `skill.time-series` for this track — FP&A forecasting is
  driver-based, not statistical time-series; tagging would pollute the
  weak-spot vocabulary.
- `spreadsheets`, `pivot tables`, `vlookup` → live on `skill.excel`
  (data-analyst.md); add-tag, do not duplicate.
- `financial modeling` — a parallel-drafted `management_consultant`
  profile may also want it. Listed as CONTESTED; if the ruling goes
  shared-entry, home it here (FMVA weights it 35% of the FA curriculum;
  consultants use models, analysts are hired for them) and let MC add a
  tag.
- `powerpoint`, `pitch deck` — same CONTESTED situation with
  management_consultant; proposed home here with an MC tag, but a
  shared-entry ruling is fine either way.
- `accounting` (bare) — claimed here, but a future wave-3 **CPA** track
  is the natural long-term owner. Ruling to record centrally: if/when CPA
  lands, `skill.accounting-fundamentals` gets the CPA tag (shared entry)
  rather than moving the alias. `gaap`/`ifrs` ride the same entry.
- Future **CFA** track (wave 3): no `cfa`, `ethics`, `fixed income`,
  `portfolio management` aliases claimed here — clean room preserved.
  `bonds` note: `portfolio` is on the deliberately-homeless list already.
- Short/noisy FTS tokens: `erp`, `sap`, `vba`, `lbo`, `dcf`, `npv`,
  `irr`, `m&a`. Trust the long aliases (`oracle financials`,
  `leveraged buyout`, `discounted cash flow`, `capital budgeting`,
  `mergers and acquisitions`) for enrichment interpretation; `dcf` and
  `lbo` are domain-distinctive enough to be usable, `erp` and `sap` are
  not (SAP-the-company vs sap-the-word in prose). `comps` deliberately
  NOT an alias (real-estate/gaming collisions); `trading comps` carries
  it. `ppt` deliberately NOT an alias (template-file noise).
- `macros` (bare) left homeless (Rust/C/Excel three-way); `excel macros`
  is the claimed form. `reporting` (bare) is on `skill.dashboards`
  (data-analyst.md) — this track's form is `management reporting`.
- Normalization legality: `fp&a`, `m&a`, `10-k`, `accretion/dilution`,
  `financial planning & analysis` all survive the normalizer (`& / -`
  preserved); no trailing-period aliases proposed.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/business-and-financial/financial-analysts.htm | role_taxonomy | BLS OOH; stable, public domain; server 403s generic fetchers — needs a browser UA |
| https://mergersandinquisitions.com/investment-banking-interview-questions/ | role_taxonomy | The free M&I/BIWS interview canon; refreshed yearly; do NOT ingest paid BIWS course material |
| https://mergersandinquisitions.com/3-statement-model/ | role_taxonomy | Free 3-statement tutorial + Excel file; stable |
| https://www.wallstreetprep.com/knowledge/build-integrated-3-statement-financial-model/ | role_taxonomy | WSP free knowledge-base guide; paid WSP courses off-limits |
| https://corporatefinanceinstitute.com/resources/career/walk-me-through-a-dcf/ | role_taxonomy | CFI free resource; stable |
| https://corporatefinanceinstitute.com/certifications/financial-modeling-valuation-analyst-fmva-program/ | role_taxonomy | FMVA syllabus with published domain weights; marketing page, occasional restructure |
| https://fpacert.financialprofessionals.org/exam/specifications | role_taxonomy | Official AFP FPAC test specifications (two parts, three domains each); stable, versioned by testing window |
| https://www.interviewpilot.app/interview-guides/financial-analyst | role_taxonomy | Loop-stage breakdown across FP&A/corp-fin flavors |
| https://www.financial-modeling.com/financial-modeling-interview-questions-guide/ | interview_report | Modeling-test formats (2–4 hr take-home, live builds); refreshed |
| https://365financialanalyst.com/career-advice/fp-a-interview-questions/ | interview_report | FP&A question walkthroughs (budget vs forecast, variance) |
| https://www.wallstreetmojo.com/financial-planning-and-analysis-interview-questions/ | interview_report | FP&A question bank; ad-heavy, content stable |
| https://www.tealhq.com/interview-questions/fp-a-analyst | interview_report | Refreshed yearly |
| https://www.tealhq.com/career-paths/financial-analyst-interview-questions | interview_report | General FA loop variant |
| https://www.venasolutions.com/blog/fpa-certifications-courses | role_taxonomy | Vendor blog surveying the FP&A cert landscape; volatile, low priority |
| (job boards: linkedin/indeed "financial analyst" + "fp&a analyst" searches) | official_job_posting | Volatile + login-gated; sample per run |

## Enrichment expectations

Expect `financial modeling`, `excel`, `budgeting`, `variance analysis`,
`dcf`, `valuation`, `financial statements` to dominate counts. Per-alias
counts matter more than usual here: `erp`/`sap`/`comps`-class tokens were
excluded or paired with long forms for exactly this reason. Zero-support
flags likely for `management reporting`, `13-week cash flow`, and the
planning-platform names (`anaplan`, `hyperion`) until postings are
layered in — keep them; résumé-resolution value stands on its own.

## Overlap with existing tracks

Near-zero overlap with all nine tech tracks except `data_analyst`: the
shared surface is exactly the Excel/SQL/Power BI/dashboards toolbelt plus
stakeholder communication, all handled as shared-entry tags, not
duplicates. No overlap with `swe`/`mle`/`quant_dev`-adjacent skills — a
quant path is a different career (math/programming-heavy) and stays out.
The deep future overlaps are the wave-3 exam careers: CFA (valuation,
accounting, corporate finance concepts) and CPA (accounting, GAAP) will
most likely **share** this track's concept entries via added tags; those
rulings are reserved for the wave-3 increments.
