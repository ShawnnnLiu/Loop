# Insurance Agent — Track Profile

**Proposed enum value:** `insurance_agent` · **Wave 5** · Research grounded
2026-07-19.

## Track decision

Own track — a licensure pipeline, not an interview loop, and one of the
purest blueprint-driven careers in the taxonomy: every state publishes an
official exam content outline per **line of authority** (life, accident &
health, property, casualty, variable/limited lines), administered by
Pearson VUE/PSI/Prometric under the state Department of Insurance. Skill
set is entirely disjoint from every tech track (zero shared v1 entries).
Large stable demand: ~47,000 projected openings/yr, +4% growth 2024–34,
median $60,370 (May 2024)
(https://www.bls.gov/ooh/sales/insurance-sales-agents.htm).

The **multi-line structure is the blueprint analog**: each line of
authority is a separate state exam with its own published outline, and the
common entry path is serial — Life (or Life & Health) first, add Property
& Casualty later, add the variable line (FINRA-gated) last. This is one
track with per-line sub-blueprints, not four tracks: the study mechanics,
regulator, exam vendor, and sales skill set are identical across lines.
State variance (pre-licensing hours, outline versions) is the
blueprint-version problem wave-3 doc §2 anticipates — model it with
taxonomy versioning + effective dates, not with per-state tracks.

**Resolver markers:** `"insurance agent"`, `"insurance sales agent"`,
`"insurance producer"`, `"insurance broker"`, `"insurance sales"`,
`"life insurance agent"`, `"health insurance agent"`,
`"property and casualty agent"`, `"p&c agent"`. Precedence hazards: never
key on bare `"agent"` (collides with `ai_engineer`'s AI-agents
vocabulary and any future real-estate marker set), bare `"broker"`
(real-estate broker, stockbroker), or bare `"producer"` (media roles).
All markers keep the "insurance" qualifier except the two long-form line
titles, which are unambiguous.

## Role snapshot

Sells life, health, property, and casualty policies; runs needs analysis
with clients, quotes and binds coverage through appointed carriers,
services renewals and claims intake. Entry requires a state producer
license per line of authority — high-school diploma typical, no degree
gate (https://www.bls.gov/ooh/sales/insurance-sales-agents.htm). Captive
(one carrier) vs independent (multi-carrier) shapes the sales workflow but
not the license path. Selling variable products additionally requires
FINRA registration (SIE + Series 6 or 7 + Series 63) under a
broker-dealer
(https://agentsync.io/blog/insurance-101/which-finra-series-exams-and-state-insurance-licenses-you-need-to-sell-variable-lines).

## Prep-process profile

- **Exam pipeline (per line of authority):** state-required pre-licensing
  study (varies: Texas requires none; Florida requires up to 200 course
  hours for the 2-20 general lines license; California repealed its
  20-hour pre-licensing mandate via AB 943 but kept 12 hours of
  ethics/code instruction —
  https://staterequirement.com/insurance-licensing/,
  https://advocacy.naifa.org/news/california-eliminates-pre-licensing-education-requirement-for-insurance-producers)
  → fingerprint background check (IdentoGO/Live Scan) → state exam at
  Pearson VUE/PSI/Prometric, typically 100–150 scored questions with a
  published content outline
  (https://www.pearsonvue.com/us/en/practicetests/insurance.html) →
  license application via state DOI or NIPR → **appointment by a
  carrier** before any policy can be sold → continuing education (~24
  hrs/2 yrs typical) to renew. Non-resident licenses ride reciprocity
  through NIPR (https://nipr.com/licensing-center).
- **Blueprint anchor (Texas, effective 2025-12-01):** Life general
  knowledge = 50 scored questions (Types of Policies 15, Riders/
  Provisions/Options/Exclusions 15, Application/Underwriting/Delivery 12,
  Retirement & Other Concepts 8) + 30-question state-specific section;
  Life & Health combined = 100 scored; P&C general = 100 scored (Types of
  Policies 22 + 23, Insurance Terms & Concepts 15 + 15, Policy Provisions
  & Contract Law 13 + 12) + 30 state-specific
  (https://www.pearsonvue.com/content/dam/VUE/vue/en/documents/publications/124401.pdf).
  Weighted sections make proportional coverage validation exact, same as
  the wave-3 careers.
- **Variable line add-on:** state life license + SIE + Series 6 (or 7) +
  Series 63, with mandatory broker-dealer sponsorship for the top-off
  exams
  (https://www.finra.org/registration-exams-ce/qualification-exams/securities-industry-essentials-exam,
  https://www.finra.org/registration-exams-ce/qualification-exams/series6).
- **Prep ecosystem note:** commercial prep (ExamFX, Kaplan, A.D. Banker)
  dominates but is copyrighted — corpus uses state outlines, DOI/NIPR/
  FINRA official pages, and free explainers only (wave-3 manifest rule).
- **Typical arc (one line, 3–6 weeks at 2–3 hrs/day):** insurance
  fundamentals + contract law → product deep-dive per outline section,
  hours ∝ published weights → state-specific statutes/ethics → timed
  practice exams to consistent passing scores → schedule exam;
  post-license: carrier appointment paperwork + prospecting ramp.

## Seed skill entries (draft)

### Existing entries — add `insurance_agent` tag (~9)

Zero v1 overlap — the 166-entry taxonomy is entirely tech. Shared entries
from other profiles (2026-07-19 reconciliation rulings):

- `skill.stakeholder-communication` (data-analyst.md; 2° — curation call).
- `skill.prospecting` (financial-advisor.md; shared FAdv+IA+REA — owns
  `prospecting`, `lead generation`, `cold calling`; `lead nurturing`
  stays on digital_marketer's `skill.marketing-automation`).
- `skill.client-management` (management-consultant.md; shared MC+FAdv+IA —
  absorbed this profile's client-retention entry; owns `client retention`,
  `book of business`, `policy renewals`).
- `skill.exam-simulation` (financial-advisor.md; the universal exam-career
  practice entry — owns `practice exams`, `question banks`, `mock exams`,
  `timed practice`).
- `skill.crm` (digital-marketer.md, 2°), `skill.salesforce`
  (salesforce-admin.md, 2°), `skill.hubspot` (digital-marketer.md, 2°) —
  replace the CRM-tools entry this profile originally drafted.
- `skill.sie-exam` + `skill.series-7` (financial-advisor.md, 2°) — the
  variable-line FINRA stack.

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.life-insurance` | Life Insurance Products | `life insurance`, `term life`, `whole life`, `universal life`, `term life insurance`, `whole life insurance`, `indexed universal life` | concept | insurance_agent | Line of authority #1; largest exam section. Variable forms live on `skill.variable-products` |
| `skill.annuities` | Annuities | `annuities`, `annuity`, `annuity valuation`, `fixed annuity`, `indexed annuity`, `immediate annuity`, `deferred annuity` | concept | insurance_agent, actuary, financial_advisor(2°) | NEW·shared (ruled 2026-07-19): defined here; actuary's separate mint folds in (contributes `annuity valuation`), financial_advisor add-tags. `variable annuity` deliberately NOT here (see variable-products) |
| `skill.health-insurance` | Health & Accident Insurance | `health insurance`, `accident and health`, `disability income insurance`, `medicare supplement`, `long term care insurance`, `long-term care insurance` | concept | insurance_agent | Line of authority #2; A&H outline: disability, medical expense, HMO/PPO, LTC |
| `skill.property-casualty` | Property & Casualty Insurance | `property and casualty`, `p&c`, `homeowners insurance`, `auto insurance`, `general liability`, `commercial lines`, `personal lines`, `workers compensation`, `errors and omissions` | concept | insurance_agent | Line of authority #3 (usually one combined exam). `p&c` is FTS noise — see notes |
| `skill.variable-products` | Variable Insurance Products | `variable products`, `variable annuity`, `variable annuities`, `variable life`, `variable universal life` | concept | insurance_agent | The FINRA-gated line; single home for all `variable *` aliases |
| `skill.series-6-63` | Series 6 & 63 | `series 6`, `series 63` | concept | insurance_agent, financial_advisor(2°) | Ruled 2026-07-19: `series 7` and `securities industry essentials` live on financial-advisor.md's per-exam entries (`skill.series-7`, `skill.sie-exam`) — this track add-tags those (2°); this entry holds the two exams that profile left unminted. `sie` still deliberately omitted (noisy token) |
| `skill.underwriting` | Underwriting Basics | `underwriting`, `field underwriting`, `insurable interest`, `risk classification` | concept | insurance_agent | Every line's outline has an underwriting section. Flagged for financial tracks — see CONTESTED |
| `skill.policy-provisions` | Policy Provisions & Riders | `policy provisions`, `policy riders`, `nonforfeiture options`, `beneficiary designations` | concept | insurance_agent | 15/50 of the life outline; the memorization core |
| `skill.insurance-contract-law` | Insurance Contract Law | `insurance contract law`, `aleatory contract`, `elements of a contract` | concept | insurance_agent | Bare `contract law` NOT claimed (future legal tracks) |
| `skill.insurance-regulation` | State Insurance Regulation | `insurance regulation`, `state insurance law`, `insurance code`, `unfair trade practices`, `insurance ethics` | concept | insurance_agent | State-specific exam section; CA keeps a 12-hr ethics requirement. Bare `compliance` lives on `skill.compliance` (CE/SA) — not claimed |
| `skill.claims-process` | Claims Process | `claims process`, `claims handling`, `notice of claim`, `proof of loss` | concept | insurance_agent | Agent-side claims intake; a future claims_adjuster track would co-tag, not re-home |
| `skill.needs-analysis` | Insurance Needs Analysis | `needs analysis`, `needs-based selling`, `financial needs analysis` | practice | insurance_agent | Life outline §IV.E; the consultative core. `suitability` CONTESTED — see notes |
| `skill.risk-transfer` | Risk Concepts & Risk Transfer | `risk transfer`, `pure risk`, `law of large numbers`, `indemnity` | concept | insurance_agent | Exam Terms & Concepts section. Bare `risk management` CONTESTED — see notes |
| `skill.social-insurance-programs` | Social Insurance Programs | `social security benefits` | concept | insurance_agent | A&H outline §VII. Ruled 2026-07-19: bare `medicare`/`medicaid` re-homed to medical_coder `skill.medicare-payer-rules` (payer-rules context wins); this track's countable Medicare term is `medicare supplement` on `skill.health-insurance` |
| `skill.consultative-selling` | Consultative Selling | `consultative selling`, `objection handling`, `closing techniques`, `cross-selling` | practice | insurance_agent, financial_advisor(2°), real_estate_agent(2°) | NEW·shared (ruled 2026-07-19): defined here; the parallel sales tracks add-tag |
| `skill.professional-networking` | Professional Networking | `professional networking`, `referral networking`, `centers of influence` | practice | insurance_agent | Bare `networking` HOMED on tech `skill.networking` (v1) — never claim; see notes |

**Optional / deferred** (protect the budget; 16 new + ~9 shared add-tags
≈ 25, far under 55): premium rating/quoting tools (carrier-specific), surplus
lines, adjuster licensing (separate career), Medicare AHIP certification
(entry `skill.ahip` if Medicare-sales users appear), retirement/qualified
plans (financial_advisor territory — tag their entry when it lands),
`skill.insurtech` platforms (Applied Epic, EZLynx).

## Alias-collision & FTS5 notes

- `networking` — homed on v1 `skill.networking` (computer networking; SA/
  CE/DO all reference it). This career uses `professional networking` /
  `referral networking` only. Do not add bare `networking` here, ever.
- `compliance` — homed on NEW·shared `skill.compliance`
  (cloud-engineer.md, CE/SA); insurance regulation gets its own entry with
  distinct aliases. `hipaa` was re-homed 2026-07-19 to medical_coder's
  `skill.hipaa-privacy` — still not claimable here.
- `p&c` — FTS5 unicode61 tokenization splits on `&`, degrading `p&c` to
  bare `p`/`c` tokens (and `c` collides with the C language alias space in
  prose). Keep it as an alias for résumé resolution, but treat its
  occurrence counts as garbage; **trust `property and casualty`** for
  enrichment.
- `sie` — noisy 3-letter token (flagged in the shared brief's noise list);
  deliberately not an alias. `securities industry essentials` is the
  countable form. Same logic: `ltc` omitted in favor of the two long
  `long term care` spellings; `e&o` omitted (same `&` problem) in favor
  of `errors and omissions`.
- `crm` — short but domain-distinctive in sales corpora; acceptable, and
  `salesforce`/`hubspot` are the trustworthy counts.
- `annuity`/`annuities` — safe, distinctive. `variable annuity` has
  exactly one home (`skill.variable-products`), keeping the FINRA-gated
  line separable from the state-only fixed/indexed products.
- Deliberately not claimed (single-home discipline): bare `contract law`,
  bare `ethics`, bare `sales`, bare `insurance` (the track marker does
  that job), bare `claims`, bare `referrals` (healthcare collision),
  bare `suitability` and `risk management` (see CONTESTED).

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/sales/insurance-sales-agents.htm | role_taxonomy | BLS OOH; US-gov public domain, annual refresh |
| https://www.pearsonvue.com/content/dam/VUE/vue/en/documents/publications/124401.pdf | role_taxonomy | Texas exam content outlines, versioned PDF w/ effective date (2025-12-01); URL churns per revision |
| https://www.pearsonvue.com/content/dam/VUE/vue/en/documents/publications/121402.pdf | role_taxonomy | Illinois exam content outlines; second state for variance coverage |
| https://www.pearsonvue.com/us/en/practicetests/insurance.html | role_taxonomy | Vendor hub page linking every state's handbook/outline; stable |
| https://www.tdi.texas.gov/agent/index.html | role_taxonomy | Texas DOI agent-licensing requirements; official, stable |
| https://www.insurance.ca.gov/0200-industry/0020-apply-license/0100-indiv-resident/ | role_taxonomy | California DOI resident-licensee requirements; official; post-AB-943 hour changes land here |
| https://nipr.com/licensing-center | role_taxonomy | Multi-state licensing/reciprocity mechanics; official |
| https://content.naic.org/cipr-topics/producer-licensing | role_taxonomy | NAIC producer-licensing overview + uniformity standards; stable |
| https://www.finra.org/registration-exams-ce/qualification-exams/securities-industry-essentials-exam | role_taxonomy | Official SIE page w/ content outline; stable, permissive |
| https://www.finra.org/registration-exams-ce/qualification-exams/series6 | role_taxonomy | Official Series 6 page w/ content outline; stable |
| https://www.iii.org/ | role_taxonomy | Insurance Information Institute free explainers (policy types, claims); industry-funded, permissive, stable |
| https://staterequirement.com/insurance-licensing/ | role_taxonomy | Per-state hours/exam/fee variance guide; free, refreshed yearly |
| https://agentsync.io/blog/insurance-101/which-finra-series-exams-and-state-insurance-licenses-you-need-to-sell-variable-lines | role_taxonomy | Clean variable-line license-stack explainer; vendor blog, moderate volatility |
| (job boards: indeed/linkedin "insurance agent" searches) | official_job_posting | Volatile + login-gated; sample per run |

Excluded on principle: ExamFX, Kaplan, A.D. Banker course content
(copyrighted commercial prep — the UWorld/Becker class of the wave-3
rule). Pass-rate statistics, where states publish them, substitute for
`interview_report` (which has no real equivalent here).

## Enrichment expectations

Expect `life insurance`, `annuities`, `underwriting`, `medicare
supplement`, `health insurance`, `property and casualty` to dominate
counts. Zero-support flags likely for `book of business` and `centers of
influence` (sales-practice prose is underrepresented in
an outline-heavy corpus) — keep them; résumé-resolution value stands.
Ignore raw counts for `p&c` and `crm` per the FTS notes. Kind
distribution will skew hard to `concept` (~15 of 20) with `tool` nearly
empty — expected per wave-3 doc §4; do not "fix" it.

## Credential-prerequisite gates (not modelable as skills)

Mirroring 03-wave-3 §1 — the Planner must refuse to schedule around
unmet gates, not treat them as weak spots:

- **Pre-licensing course hours** where the state mandates them (0 in TX;
  up to 200 in FL; 12 ethics-only in CA post-AB-943) — a hard sequencing
  gate before exam registration, with state-by-state variance.
- **Fingerprint/background check** — external latency; felony findings
  can bar licensure entirely.
- **Per-line exam pass** — each added line of authority is its own gate;
  serial multi-line plans have gate chains (Life → P&C → variable).
- **Carrier appointment** — no selling until a carrier appoints the
  licensee; employer-shaped, unschedulable.
- **FINRA broker-dealer sponsorship** — required before Series 6/7
  top-off registration; the variable line is double-gated (state license
  AND FINRA registration).
- **Continuing education** (~24 hrs/2 yrs typical) — recurring renewal
  gate, a natural fit for recurring scheduled blocks.

## Overlap with existing tracks

None with any tech track — zero shared v1 entries. The parallel-sales
overlap was ruled 2026-07-19: this profile keeps the insurance product
vocabulary (`skill.annuities` now shared with actuary/financial_advisor;
`skill.consultative-selling` shared with the sales tracks) and add-tags
the shared client-acquisition entries homed elsewhere
(`skill.prospecting` in financial-advisor.md, `skill.client-management`
in management-consultant.md, `skill.exam-simulation` — the single
universal exam-practice entry — in financial-advisor.md).
