# Personal Financial Advisor — Track Profile

**Proposed enum value:** `financial_advisor` · **Wave 5** · Research grounded
2026-07-19.

## Track decision

Own track — an exam/licensure career (wave-5 sibling of the wave-3 five in
`../03-wave-3-exam-careers.md`) with a fully standardized, governing-body
ladder: SIE → Series 7 (firm-sponsored) → Series 65/66 → CFP later. Every
rung has an official, versioned, weighted content outline from FINRA,
NASAA, or CFP Board — exactly the `role_taxonomy` anchor class the corpus
wants. Demand is strong: BLS projects +10% employment growth 2024–34
(much faster than average), ~24,100 openings/yr, median pay $102,140
(May 2024)
(https://www.bls.gov/ooh/business-and-financial/personal-financial-advisors.htm).

Two deliberate boundaries against finance neighbors:

- **Not `cfa` (wave 3).** CFA is the charterholder/institutional path
  (buy-side research, portfolio analytics, ~300–400 hrs/level over ~4
  years). `financial_advisor` is client-facing retail wealth management:
  licensing exams measured in weeks-to-months, suitability and
  client-acquisition skills the CFA curriculum barely touches. The CFA
  track keeps `cfa`, `chartered financial analyst`, and
  institutional-analysis vocabulary; this track never claims them.
- **Not `financial_analyst` (parallel FP&A/corporate-finance track).**
  Analysts build models (three-statement, DCF, `npv`/`irr`, `fp&a`);
  advisors pass licensure and manage client books. This profile claims no
  modeling/valuation aliases. The one dangerous seam is the literal string
  `financial planning` (advisory practice) vs "financial planning and
  analysis" (FP&A) — see Alias-collision notes and marker precedence
  below.

**Resolver markers:** `"financial advisor"`, `"personal financial
advisor"`, `"financial planner"`, `"certified financial planner"`,
`"wealth management"`, `"wealth manager"`, `"wealth advisor"`,
`"investment adviser representative"`, `"registered representative"`,
`"series 7"`. Precedence hazards: (a) `financial_analyst`'s markers
(`"financial analyst"`, `"fp&a"`, `"financial planning and analysis"`)
must be checked **before** this track if a bare `"financial planning"`
marker is ever added here — this profile deliberately uses `"financial
planner"` (person-noun) instead to avoid substring capture of FP&A
titles; (b) insurance-track titles sometimes read "financial advisor" at
insurance-heavy firms — acceptable capture, the prep ladder is the same
FINRA/state stack; (c) none of the existing tech-track markers (swe, mle,
data_*, etc.) share any token with these.

## Role snapshot

Advises individuals on investments, retirement, insurance coverage, tax
impact, and estate plans; typical entry is a bachelor's degree plus
on-the-job licensing — the license ladder, not a graduate degree, is the
entry credential
(https://www.bls.gov/ooh/business-and-financial/personal-financial-advisors.htm).
Sellers of securities must pass FINRA exams; advisers charging fees for
advice register via NASAA's Series 65/66. The commercial prep market
(Kaplan, Achievable, STC, ExamFX) is large and aggressively copyrighted —
corpus policy is official outlines + free explainers only, per the wave-3
rule.

## Prep-process profile

- **Exam pipeline (the "interview loop" of this track):**
  1. **SIE** — 75 questions, 1h45m, passing 70, $100; **no firm
     association required**; results valid four years
     (https://www.finra.org/registration-exams-ce/qualification-exams/securities-industry-essentials-exam).
     Sections: Knowledge of Capital Markets 16% (12q), Understanding
     Products and Their Risks 44% (33q), Understanding Trading, Customer
     Accounts and Prohibited Activities 31% (23q), Overview of the
     Regulatory Framework 9% (7q).
  2. **Series 7 (top-off)** — 125 questions, 3h45m, passing 72, $395;
     **requires sponsorship by a FINRA member firm** (Form U4); SIE is a
     co-requisite
     (https://www.finra.org/registration-exams-ce/qualification-exams/series7).
     Four job functions: F1 Seeks Business 9q, F2 Opens Accounts 11q,
     F3 Provides Information/Recommendations 91q (~73% — the exam is
     mostly suitability + products), F4 Processes Transactions 14q.
  3. **Series 65 or 66 (state/IAR)** — Series 65: 130 scored questions,
     180 min, pass 92/130; sections Economic Factors & Business
     Information 15% (20q), Investment Vehicle Characteristics 25% (32q),
     Client Recommendations & Strategies 30% (39q), Laws/Regulations/
     Ethics 30% (39q)
     (https://www.nasaa.org/wp-content/uploads/2023/02/Series-65-Outline-June-2023.pdf,
     effective June 2023 — blueprint-version mapping applies). Series 66:
     100 scored questions, 150 min, pass 73, equivalent to 63+65 combined
     but with Series 7 as co-requisite
     (https://www.finra.org/registration-exams-ce/qualification-exams/series66).
     **Neither NASAA exam requires sponsorship** — unsponsored candidates
     self-enroll via FINRA and get a 120-day test window
     (https://www.nasaa.org/exams/exam-faqs/).
  4. **CFP (later-career)** — 170 questions across eight weighted
     principal-knowledge domains: Professional Conduct & Regulation 8%,
     General Principles 15%, Risk Management & Insurance Planning 11%,
     Investment Planning 17%, Tax Planning 14%, Retirement Savings &
     Income Planning 18%, Estate Planning 10%, Psychology of Financial
     Planning 7%
     (https://www.cfp.net/get-certified/certification-process/exam-requirement/about-the-cfp-exam/what-youll-be-tested-on).
- **Credential-prerequisite gates (not skills — Planner must refuse to
  schedule around them, per `../03-wave-3-exam-careers.md`):**
  - Series 7 (and 6) **cannot even be sat** without FINRA member-firm
    sponsorship — the gate is employment, not knowledge. SIE and Series
    65/66 have no such gate; a sensible unsponsored plan is SIE + 65.
  - Sequencing is hard: SIE before/with Series 7; Series 7 co-requisite
    for Series 66 (but not 65). Mirrors CFA level-sequencing.
  - SIE results expire after four years — a validity clock, another
    non-skill constraint.
  - CFP gates: bachelor's degree, CFP Board registered coursework, and
    6,000 hours of professional experience (or 4,000 apprenticeship) —
    years-scale gates the taxonomy cannot model as entries.
  - Selling variable annuities/insurance also needs **state insurance
    licenses** (state-by-state, out of scope for seed entries).
- **Anchor resources:** the official FINRA content outlines (SIE, Series
  7) and NASAA test specifications (65/66) — each publishes per-section
  question counts, so blueprint-proportional coverage validation applies
  directly; CFP Board's principal-knowledge topic list. Free explainers
  (Investopedia exam pages, investor.gov) for concept coverage. **Never
  ingest Kaplan/Achievable/STC/ExamFX material.**
- **Typical arc:** ~2–4 weeks SIE (foundations + products vocabulary) →
  sponsored hires: 3–6 weeks Series 7 top-off drilling weighted to F3 →
  2–4 weeks Series 65/66 (regulations + suitability casework) →
  question-bank drilling and timed simulated exams throughout, hour
  budgets ∝ published section weights → in parallel at most firms:
  prospecting scripts, CRM hygiene, and mock client meetings (advisor
  training programs grade client acquisition as heavily as licensure).

## Seed skill entries (draft)

### Existing entries — add `financial_advisor` tag

Almost nothing: the 166-entry v1 taxonomy is tech-only and contains zero
finance-adjacent aliases (verified by grep). Candidates from the shared
registry, all subject to reconciliation:

- `skill.excel` (NEW·shared, defined in `data-analyst.md`) — advisor
  planning worksheets; secondary (2°) tag.
- `skill.stakeholder-communication` (NEW·shared, data-analyst.md) —
  defensible 2° for client conversations; this profile also seeds a
  distinct advisor-specific `skill.client-relationship-management`
  (retention/book-management, a different practice than readout
  communication).
- `skill.compliance` (NEW·shared, defined in cloud-engineer.md, CE/SA) —
  homed there; requesting add-tag `financial_advisor` (2°) via CONTESTED
  rather than minting a regulatory-compliance twin. This track's own
  regulatory vocabulary lives on `skill.securities-regulation` below.
- **Ruled 2026-07-19 (reconciliation):** `skill.client-management`
  (management-consultant.md; shared MC+FAdv+IA — owns `client
  relationship management`, `client relationships`, `book of business`;
  absorbed this profile's client-relationship-management draft entry);
  `skill.crm` (digital-marketer.md, 2° — `redtail` suggested there as an
  optional alias); `skill.annuities`, `skill.variable-products`,
  `skill.health-insurance` (insurance-agent.md, 2° — see
  insurance-planning row); `skill.series-6-63` (insurance-agent.md, 2°);
  `skill.consultative-selling` (insurance-agent.md, 2°).

### New entries

Kind skew is expected and correct for an exam career (`concept`-heavy,
near-zero `tool`/`language`) — do not "balance" it.

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.sie-exam` | SIE (Securities Industry Essentials) | `securities industry essentials`, `sie exam`, `sie` | concept | financial_advisor, insurance_agent(2°) | Gateway exam, no sponsorship; shared with the insurance variable line (ruled 2026-07-19). `sie` is a noisy short FTS token — trust `securities industry essentials` |
| `skill.series-7` | Series 7 (General Securities Representative) | `series 7`, `general securities representative`, `series 7 top-off` | concept | financial_advisor, insurance_agent(2°) | Firm-sponsorship gate; F3 is 73% of the exam. Shared with the insurance variable line (ruled 2026-07-19) |
| `skill.series-65` | Series 65 (Investment Adviser Law) | `series 65`, `uniform investment adviser law exam` | concept | financial_advisor | No sponsorship; the fee-only/IAR path |
| `skill.series-66` | Series 66 (Combined State Law) | `series 66`, `uniform combined state law exam` | concept | financial_advisor | Equivalent to 63+65; Series 7 co-requisite |
| `skill.cfp-certification` | CFP Certification | `cfp`, `certified financial planner` | concept | financial_advisor | Later-career; degree + coursework + 6,000-hr gates |
| `skill.financial-planning` | Financial Planning | `financial planning`, `comprehensive financial planning`, `financial plan development`, `cash flow planning` | concept | financial_advisor | `financial planning` vs FP&A seam — see collision notes |
| `skill.retirement-planning` | Retirement Planning | `retirement planning`, `retirement income planning`, `401k`, `ira`, `roth ira`, `social security` | concept | financial_advisor | Heaviest CFP domain (18%) |
| `skill.estate-planning` | Estate Planning | `estate planning`, `wealth transfer`, `trusts and estates` | concept | financial_advisor | Bare `trusts` deliberately not claimed (English collision) |
| `skill.tax-planning` | Tax Planning | `tax planning`, `tax-advantaged accounts`, `tax loss harvesting` | concept | financial_advisor | CFP 14%. A future `cpa` track owns deep tax vocabulary — this entry stays advisory-scoped |
| `skill.insurance-planning` | Insurance Planning | `insurance planning`, `insurance products` | concept | financial_advisor | Ruled 2026-07-19: `annuities`, `variable annuities`, `long-term care insurance`, `life insurance` all live on insurance-agent.md's entries (`skill.annuities`, `skill.variable-products`, `skill.health-insurance`, `skill.life-insurance`) — this track add-tags them (2°) |
| `skill.investment-products` | Securities Products | `mutual funds`, `etfs`, `exchange-traded funds`, `options trading`, `municipal securities` | concept | financial_advisor | SIE's 44% section. `equities`/`fixed income` NOT claimed — contested with financial_analyst/cfa |
| `skill.asset-allocation` | Asset Allocation | `asset allocation`, `diversification`, `modern portfolio theory`, `rebalancing` | concept | financial_advisor | `cfa` will co-tag when it lands; `portfolio management` left contested |
| `skill.suitability` | Suitability & Know Your Customer | `suitability`, `know your customer`, `kyc`, `regulation best interest`, `reg bi`, `risk tolerance` | concept | financial_advisor | Core discriminator of this track. `kyc` also banking/fintech usage — flag |
| `skill.securities-regulation` | Securities Regulation | `securities regulation`, `finra rules`, `sec rules`, `investment advisers act`, `blue sky laws` | concept | financial_advisor | 30% of Series 65; 9% of SIE |
| `skill.fiduciary-duty` | Fiduciary Duty & Ethics | `fiduciary duty`, `fiduciary standard`, `fiduciary` | concept | financial_advisor | `fiduciary` alone is prose-common in finance docs — trust the two-word forms |
| `skill.customer-accounts` | Customer Accounts & Trading | `customer accounts`, `account opening`, `order types`, `margin accounts`, `trade settlement` | concept | financial_advisor | SIE section 3 (31%) + Series 7 F2/F4 |
| `skill.behavioral-finance` | Behavioral Finance | `behavioral finance`, `investor psychology`, `psychology of financial planning` | concept | financial_advisor | New CFP domain (7%) |
| `skill.prospecting` | Prospecting & Client Acquisition | `prospecting`, `lead generation`, `lead gen`, `cold calling`, `client acquisition`, `sphere of influence` | practice | financial_advisor, insurance_agent, real_estate_agent | NEW·shared (ruled 2026-07-19): defined HERE for all three sales tracks; absorbed real-estate's lead-gen mint. `lead nurturing`/`lead scoring` stay on digital_marketer's `skill.marketing-automation`; digital_marketer keeps `demand generation` instead |
| `skill.financial-planning-software` | Financial Planning Software | `financial planning software`, `emoney`, `moneyguidepro`, `rightcapital` | tool | financial_advisor | The track's only advisor-specific tooling |
| `skill.exam-simulation` | Timed Exam Simulation | `practice exams`, `practice tests`, `mock exams`, `question banks`, `timed practice`, `timed practice tests`, `test-taking strategies` | practice | financial_advisor + all exam careers | NEW·shared (ruled 2026-07-19): the single universal exam-practice entry, defined HERE; tracks = teacher_k12, real_estate_agent, insurance_agent, actuary, medical_coder, electrician now, wave-3 careers (cpa/cfa/pmp/nclex/bar) when they land. Absorbed insurance-agent's timed-practice-exams mint |

**Optional / deferred** (protect the budget; add only on enrichment or
user demand): Series 63 as its own entry (subsumed by 66), Series 6,
ChFC/CLU designations, `skill.education-planning` (`529 plans`, `college
savings`), `skill.time-value-of-money` (expected to be homed by
`financial_analyst` — advisor add-tags later), state insurance licensing,
referral marketing.

Running total: 20 new + ~10 shared add-tags ≈ **30 entries** — far under
the ~55 self-cap and the ~100 prompt budget.

## Alias-collision & FTS5 notes

- **Zero v1 collisions** — no finance-adjacent alias exists in
  `skill_taxonomy_v1.json` (grepped for
  finance/portfolio/retirement/estate/tax/insurance/sales/crm/etc.).
- **`networking` is OWNED by v1 `skill.networking` (computer networks).**
  Advisor "networking/referrals" must never claim it; deferred as
  `referral marketing` if ever needed.
- **`financial planning` seam:** as an exact alias string it is unique
  (alias uniqueness is exact-match, so `fp&a`'s "financial planning and
  analysis" can coexist on a financial_analyst entry), but FTS5
  occurrence counting will match the bigram inside FP&A prose —
  enrichment counts for `skill.financial-planning` are optimistic; trust
  `comprehensive financial planning`. Resolver-marker side handled by
  using `financial planner` (see Track decision).
- **Contested tokens — ruled 2026-07-19:** this profile WON the homes for
  `prospecting`/`lead generation`/`cold calling` (skill.prospecting,
  shared with insurance/real-estate) and the `practice exams` family
  (skill.exam-simulation, shared with every exam career). It CEDED
  `crm`/`salesforce` (digital-marketer.md / salesforce-admin.md),
  `annuities`/`variable annuities`/`long-term care insurance`/`life
  insurance` (insurance-agent.md), `client relationship management`/`book
  of business` (management-consultant.md's skill.client-management), and
  never claimed `equities`, `fixed income`, `portfolio management`,
  `time value of money` (financial_analyst and wave-3 cfa territory) or
  `compliance` (add-tag 2° on the cloud-engineer.md home).
- **Deliberately homeless respected:** bare `portfolio` (already on the
  02-doc homeless list), bare `trusts`, bare `options`, bare `bonds`,
  bare `ethics` — all ordinary-English FTS noise; only multi-word forms
  are seeded.
- **Short/noisy tokens flagged:** `sie` (trust `securities industry
  essentials`), `kyc` (trust `know your customer`), `crm` (acronym is
  distinctive but sales-generic — trust per-alias counts), `cfp` (not an
  English word; acceptable), `fiduciary` (prose-common in finance corpus —
  trust `fiduciary duty`).
- Numerals survive normalization, so `series 7`, `401k`, `529 plans` are
  legal, distinctive aliases — the exam-ladder names are actually this
  track's *best* FTS tokens.

## Candidate corpus sources (manifest seeds)

Official blueprints + free explainers only; never commercial prep
(Kaplan, Achievable, STC, ExamFX, TestGeek-class sites).

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/business-and-financial/personal-financial-advisors.htm | role_taxonomy | BLS OOH; stable, public domain; bot-blocks (403) — fetch may need UA care |
| https://www.finra.org/registration-exams-ce/qualification-exams | role_taxonomy | FINRA exam-ladder hub; stable |
| https://www.finra.org/registration-exams-ce/qualification-exams/securities-industry-essentials-exam | role_taxonomy | Official SIE page + linked content-outline PDF; stable, revision-stamped |
| https://www.finra.org/registration-exams-ce/qualification-exams/series7 | role_taxonomy | Official Series 7 page + outline PDF; stable |
| https://www.finra.org/registration-exams-ce/qualification-exams/series65 | role_taxonomy | FINRA-administered NASAA exam page |
| https://www.finra.org/registration-exams-ce/qualification-exams/series66 | role_taxonomy | Co-requisite rules live here |
| https://www.nasaa.org/wp-content/uploads/2023/02/Series-65-Outline-June-2023.pdf | role_taxonomy | Official NASAA test specifications with per-topic question counts; versioned URL — re-check for post-2023 revision at ingest |
| https://www.nasaa.org/exams/exam-faqs/ | role_taxonomy | Sponsorship-not-required + 120-day-window rules; stable |
| https://www.cfp.net/get-certified/certification-process/exam-requirement/about-the-cfp-exam/what-youll-be-tested-on | role_taxonomy | Eight CFP domains + weights; 2026 topic update in effect — version-map old/new |
| https://www.cfp.net/get-certified/certification-process | role_taxonomy | The 4E gates (education/exam/experience/ethics); stable |
| https://www.investor.gov/introduction-investing/getting-started/working-investment-professional | role_taxonomy | SEC investor-ed explainer of adviser vs broker roles; public domain |
| https://www.investopedia.com/articles/financialcareers/07/financial_advisor.asp | role_taxonomy | Free career-path explainer; refreshed periodically |
| https://www.cfp.net/get-certified/certification-process/exam-requirement/about-the-cfp-exam/exam-statistics | interview_report | Pass-rate statistics — the exam-career substitute for interview banks (per 03-doc); updated per administration |
| (job boards: linkedin/indeed "financial advisor" searches) | official_job_posting | Volatile + login-gated; sample per run, 45-day decay |

## Enrichment expectations

`series 7`, `financial planning`, `retirement planning`, `mutual funds`,
`suitability`, `annuities` should dominate counts across the official
outlines. Expect zero-support flags for `emoney`/`moneyguidepro`/
`rightcapital` (planning software appears in postings, not blueprints — fix by
growing the posting layer, keep the entries) and for `sie` undercount
paradox in reverse: `sie` will overcount (substring-safe FTS mitigates,
but prose collisions remain) — read the per-alias report, trust
`securities industry essentials`. `financial planning` counts inflated by
any FP&A documents that enter neighboring tracks' corpora; per-track
counting keeps this contained.

## Overlap with existing tracks

Effectively **zero overlap with all nine live tech tracks** — the only
shared surfaces are generic (`excel`, stakeholder communication). The real
adjacencies are unbuilt: wave-3 `cfa` (shares asset-allocation/products
vocabulary; boundary = institutional charter vs retail licensing),
parallel `financial_analyst` (boundary = modeling/valuation vs
licensure/suitability; no shared markers by construction), and the
parallel insurance/real_estate sales tracks (shared client-acquisition
practice entries — the CONTESTED block). This is also the first landed
track to exercise the credential-prerequisite gate concept from
`../03-wave-3-exam-careers.md`: firm sponsorship for Series 7 is the
canonical "gate the Planner must refuse to schedule around."
