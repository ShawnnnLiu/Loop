# Actuary — Track Profile

**Proposed enum value:** `actuary` · **Wave 5** · Research grounded
2026-07-19.

## Track decision

Own track — arguably the most codified multi-year exam ladder anywhere:
a governing body (SOA or CAS) publishes versioned, weighted syllabi per
exam, per-sitting pass rates, and an explicit credential sequence
(https://www.soa.org/education/exam-req/edu-asa-req/,
https://www.casact.org/credential-requirements). Candidates budget
roughly 100 study hours per exam hour — ~300+ hours per preliminary exam
(https://www.beanactuary.org/actuarial-exams/what-does-it-take/) — for
4–7+ years to associateship. Skill set is nearly disjoint from every
existing track except a statistics/R/Python/Excel/SQL core shared with
the data careers. One track covers both bodies: the **SOA vs CAS fork**
(life/health/pension/finance vs property & casualty) is a
pipeline-branching decision *inside* the track, mirroring the NCLEX-vs-bar
distinction in `../03-wave-3-exam-careers.md` — the preliminary exams are
shared (CAS accepts SOA Exams P and FM as its Exams 1 and 2), and the
paths diverge only after them.

**Resolver markers:** `"actuary"`, `"actuarial"`, `"actuarial analyst"`,
`"actuarial associate"`, `"actuarial science"`, `"pricing actuary"`,
`"reserving actuary"`. The `actuar` stem is distinctive; no existing
track's markers collide. One precedence hazard: hybrid titles like
"actuarial data scientist" contain the `data_scientist` marker — insert
the `actuary` tuple **before** `data_scientist` in `_TRACK_MARKERS` so
`actuarial` wins. Do NOT use `asa`, `fsa`, `acas`, `fcas` as markers:
short tokens with heavy outside meanings (FSA = flexible spending
account; ASA = American Statistical Association).

## Role snapshot

Quantifies insurance and financial risk — pricing products, setting
reserves, projecting liabilities — using probability, financial
mathematics, and statistical models. BLS projects **22% growth
2024–2034** (much faster than average) with median pay **$125,770**
(May 2024), but only **~2,400 openings per year** — a small-headcount
occupation (https://www.bls.gov/ooh/math/actuaries.htm). Honest sizing:
this track will never drive volume the way `swe` or `data_analyst` do.
It earns its place on product fit instead — candidates schedule 300+
hours per exam against a published, weighted blueprint for years on end,
which is close to the ideal input for a deterministic study planner.
Hiring loops for entry roles are light (behavioral + technical basics);
**exam progress is the credential**, so the prep object is the exam
ladder, not an interview loop.

## Prep-process profile

- **Exam pipeline (SOA/ASA path):** Exam P (Probability) → Exam FM
  (Financial Mathematics) → FAM (Fundamentals of Actuarial Mathematics)
  → ASTAM *or* ALTAM (short-term vs long-term advanced mathematics) +
  SRM (Statistics for Risk Modeling) → PA (Predictive Analytics, an
  R-based analysis), plus VEE credits, the PAF/ASF/FAP e-Learning
  modules, and the Associateship Professionalism Course
  (https://www.soa.org/education/exam-req/edu-asa-req/). Order is
  formally flexible but effectively sequential — FAM assumes P and FM;
  ASTAM/ALTAM assume FAM. **CAS/ACAS fork:** shared P and FM (as Exams
  1/2), then MAS-I, MAS-II, Exam 5 (ratemaking/reserving), Exam 6
  (regulation), the new PCPA predictive-analytics requirement, DISC
  online courses, and the Course on Professionalism after five exams
  (https://www.casact.org/credential-requirements).
- **Credential-prerequisite gates (not skills — mirror
  `../03-wave-3-exam-careers.md`):** a bachelor's degree (typical);
  **VEE** in Economics, Accounting & Finance, and Mathematical
  Statistics, earned via approved university coursework and claimable
  only *after two passed exams*
  (https://www.soa.org/education/exam-req/edu-vee/); sequential exam
  dependencies; fixed exam sittings with registration deadlines (P and
  FM run ~6 sittings/year; upper exams 1–4). The taxonomy cannot model
  any of these as skills — the Planner must be able to refuse to
  schedule around an unmet gate, and exam windows are hard external
  deadlines for the Scheduler (wave-3 adaptations #1 and #3 apply
  verbatim).
- **Anchor resources:** official per-sitting syllabi with published
  topic weights — Exam P weights univariate random variables 44–50%,
  general probability and multivariate each ~23–30%
  (https://www.soa.org/globalassets/assets/files/edu/2026/spring/syllabi/2026-05-exam-p-syllabus.pdf);
  Exam FM weights annuities/loans heaviest
  (https://www.soa.org/globalassets/assets/files/edu/2026/syllabi/2026-06-exam-fm-syllabus.pdf);
  CAS Syllabus of Basic Education
  (https://www.casact.org/sites/default/files/2025-01/2025_SOBE.pdf).
  Per-sitting pass rates are published — P/FM historically ~40–55%
  (https://www.soa.org/education/exam-results/,
  https://www.actuarial-lookup.com/exams/soa). "Plan hours per topic ∝
  published weight" is standard advice, exactly what coverage validation
  checks deterministically.
- **Typical per-exam arc (12–16 weeks, ~300 hrs at ~20 hrs/wk):**
  source reading through the full syllabus → topic-by-topic mastery
  proportional to blueprint weight → question-bank drilling with error
  logs → timed full-length practice exams in the final 3–4 weeks
  (https://www.beanactuary.org/actuarial-exams/what-does-it-take/,
  https://etchedactuarial.com/how-long-does-it-take-to-study-for-exam-p/).
  The multi-year meta-arc — one or two exams per year alongside a
  full-time job with employer study hours — is the actual product-fit
  story.

## Seed skill entries (draft)

Kind distribution is deliberately `concept`-heavy with near-empty
`language`/`framework` — the wave-3 skew; do not add validation that
assumes kind balance.

### Existing entries — add `actuary` tag (~10)

`skill.probability` (v1 — Exam P core; consider adding aliases
`exam p`, `probability theory`), `skill.statistics` (v1 — consider
adding alias `mathematical statistics`, the VEE topic name), `skill.r`
(v1 — the Exam PA / SRM language; `r` remains unusable for FTS
counting), `skill.python` (v1), `skill.sql` (v1), `skill.excel`
(NEW·shared, defined in `data-analyst.md` — the actuarial lingua
franca), `skill.time-series` (v1 — owns `forecasting`; SRM/MAS-II
topic), `skill.regression-analysis` (NEW·shared, `data-analyst.md`),
`skill.hypothesis-testing` (NEW·shared, `data-analyst.md` — VEE
mathematical statistics), `skill.stakeholder-communication` (NEW·shared,
`data-analyst.md`; secondary — communicating results to non-actuaries
appears in most postings).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.financial-mathematics` | Financial Mathematics | `financial mathematics`, `exam fm`, `interest theory`, `theory of interest` | concept | actuary | Exam FM core; `fm` bare is an unusable FTS token — the `exam fm` long form is the alias. `time value of money` ruled 2026-07-19 to `skill.corporate-finance` (financial-analyst.md) |
| `skill.annuities` | Annuities | *(see insurance-agent.md)* | concept | insurance_agent, actuary, financial_advisor(2°) | NEW·shared (ruled 2026-07-19): defined in insurance-agent.md, which absorbed this profile's mint and its `annuity valuation` alias — listed here for the actuary tag |
| `skill.life-contingencies` | Life Contingencies | `life contingencies`, `survival models`, `life tables`, `mortality tables` | concept | actuary | FAM-L/ALTAM core; `survival analysis` deliberately NOT claimed (data_scientist-adjacent phrasing) |
| `skill.loss-models` | Loss Models | `loss models`, `severity distributions`, `frequency severity`, `aggregate losses` | concept | actuary | FAM-S/ASTAM and CAS MAS material |
| `skill.credibility-theory` | Credibility Theory | `credibility theory`, `buhlmann credibility` | concept | actuary | Bare `credibility` deliberately omitted — ordinary English prose noise |
| `skill.reserving` | Loss Reserving & Valuation | `reserving`, `loss reserving`, `chain ladder`, `ibnr`, `actuarial valuation` | practice | actuary | CAS Exam 5 / valuation work; `ibnr` is short but non-English, usable |
| `skill.ratemaking` | Ratemaking | `ratemaking`, `rate making`, `insurance pricing`, `rate indications` | practice | actuary | CAS Exam 5; bare `pricing` deliberately unclaimed (PM strategy casework uses it) |
| `skill.enterprise-risk-management` | Enterprise Risk Management | `enterprise risk management`, `erm` | concept | actuary | Bare `risk management` CONTESTED (CFA/PMP-class drafts); `erm` short but distinctive |
| `skill.stochastic-processes` | Stochastic Processes | `stochastic processes`, `stochastic modeling`, `markov chains`, `monte carlo simulation`, `monte carlo` | concept | actuary | MAS-I/quant-adjacent; a future quant track add-tags rather than re-minting |
| `skill.glm` | Generalized Linear Models | `generalized linear models`, `glm`, `glms` | concept | actuary | MAS-I/SRM/PA core; data_scientist is a natural secondary tag |
| `skill.predictive-analytics` | Predictive Analytics | `predictive analytics`, `exam pa` | concept | actuary | Exam PA; `predictive modeling` listed as CONTESTED (data_scientist phrasing) rather than claimed |
| `skill.sas` | SAS | `sas`, `base sas` | tool | actuary | Common in insurance/health shops; data_scientist secondary candidate; short-token count is advisory |
| `skill.vba` | VBA | *(see financial-analyst.md)* | language | financial_analyst, actuary | NEW·shared (ruled 2026-07-19): defined in financial-analyst.md (identical mint, `vba`/`excel macros`/`visual basic for applications`) — listed here for the actuary tag; DA add-tags later if demand shows |
| `skill.asset-liability-management` | Asset-Liability Management | `asset liability management`, `alm`, `immunization`, `duration matching` | concept | actuary | FM portfolio topics; `fixed income`/`derivatives`/`duration` bare left for a CFA-class draft |
| `skill.reinsurance` | Reinsurance | `reinsurance` | concept | actuary | Distinctive posting term; excellent FTS signal |
| `skill.pensions` | Pensions & Retirement Benefits | `pensions`, `pension valuation`, `retirement benefits` | concept | actuary | Retirement practice area / EA-adjacent roles |
| `skill.statutory-reporting` | Statutory & Financial Reporting | `statutory reporting`, `ifrs 17`, `ldti` | concept | actuary | Valuation-role postings; bare `financial reporting` left for a CPA-class draft |

**Optional / deferred** (protect the ≤100 budget; add only if enrichment
or user demand supports them): actuarial modeling software as an entry —
its dominant names collide badly (`prophet` vs the Facebook forecasting
library `data-scientist.md` already considered for `skill.time-series`;
`axis` is generic prose) so it needs multi-word aliases like
`moody's axis` if ever minted; exam-drilling as a `practice` entry;
`economic capital`; `solvency ii`; mortality improvement models.

Running total: ~10 existing + 17 new ≈ **27 entries**, far under the
~100 prompt budget — appropriate for a small-headcount track.

## Alias-collision & FTS5 notes

- `p` and `fm` are unusable-short FTS tokens; the long forms `exam p`
  (suggested on existing `skill.probability`) and `exam fm` (on
  `skill.financial-mathematics`) are the countable aliases. Same logic
  as the known `r` limitation.
- `probability`, `statistics`, `r`, `python`, `sql`, `forecasting` are
  already homed on v1 entries — tag, don't mint.
- `model validation` is owned by v1 `skill.model-evaluation`. Actuarial
  model-validation roles exist; if the track needs it, add-tag that
  entry — do not re-mint.
- CONTESTED (central reconciliation decides; this profile does not
  assume it wins): `annuities` (vs the parallel insurance_agent draft),
  bare `risk management` (vs CFA/PMP-class drafts), `predictive
  modeling` (vs data_scientist), `derivatives` / `fixed income` (vs
  CFA-class), `underwriting` / `life insurance` (insurance_agent is the
  likely home; actuary add-tags second), `economics` (VEE topic name,
  but a CFA-class draft and gate-not-skill logic both argue against
  claiming it here).
- `prophet` is deliberately unclaimed by this track despite Prophet
  being major actuarial software — `data-scientist.md` already
  considered it as a time-series alias and the FTS collision is
  hopeless. Treat it like the "deliberately homeless" list unless
  reconciliation rules otherwise.
- Short-but-distinctive tokens `erm`, `alm`, `glm`, `sas`, `ibnr`: not
  ordinary English, so usable, but treat their raw counts as advisory
  and trust the multi-word siblings (`enterprise risk management`,
  `generalized linear models`, …) per the mechanics doc.
- Bare `credibility` and bare `pricing` are deliberately omitted —
  ordinary-prose noise / cross-track ambiguity.

## Candidate corpus sources (manifest seeds)

Manifest rule from `../03-wave-3-exam-careers.md` applies: official
blueprints + free explainers only. Never ingest commercial prep material
(Coaching Actuaries, The Infinite Actuary, ACTEX/ASM manuals — the
UWorld/Kaplan/Becker class of this profession).

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/math/actuaries.htm | role_taxonomy | BLS OOH; public-domain, stable; server 403s generic fetchers — ingest tool may need a browser UA |
| https://www.soa.org/education/exam-req/edu-asa-req/ | role_taxonomy | Canonical ASA requirement set (exams, VEE, modules); stable, official |
| https://www.soa.org/globalassets/assets/files/edu/2026/spring/syllabi/2026-05-exam-p-syllabus.pdf | role_taxonomy | Official weighted Exam P blueprint; URL churns per sitting — re-pin each snapshot |
| https://www.soa.org/globalassets/assets/files/edu/2026/syllabi/2026-06-exam-fm-syllabus.pdf | role_taxonomy | Official weighted Exam FM blueprint; same per-sitting URL churn |
| https://www.soa.org/education/exam-req/edu-vee/ | role_taxonomy | VEE topics + the two-exams-first prerequisite; official, stable |
| https://www.soa.org/education/exam-results/ | role_taxonomy | Official per-sitting pass rates; updated every sitting (volatile by design, keep) |
| https://www.casact.org/credential-requirements | role_taxonomy | ACAS/FCAS requirements incl. PCPA and DISCs; official, stable |
| https://www.casact.org/sites/default/files/2025-01/2025_SOBE.pdf | role_taxonomy | CAS Syllabus of Basic Education; revised annually with announced effective dates |
| https://www.beanactuary.org/actuarial-exams/what-does-it-take/ | role_taxonomy | Joint SOA/CAS outreach site; study-hour norms; stable |
| https://www.actuarial-lookup.com/exams/soa | role_taxonomy | Third-party pass-rate aggregator; useful history, unclear license — verify before ingest |
| https://actuary.info/become-an-actuary/actuarial-exams/ | role_taxonomy | Free 2026 SOA+CAS pathway guide; refreshed yearly |
| https://etchedactuarial.com/how-long-does-it-take-to-study-for-exam-p/ | interview_report | Free exam-experience explainer (personal blog; link-rot risk) |
| https://www.reddit.com/r/actuary/wiki/index | interview_report | Community exam-experience wiki — the profession's question-bank-adjacent lore; volatile, licensing unclear |
| https://www.dwsimpson.com/salary/ | official_job_posting | Recruiter salary survey + live postings; volatile, sample per run |
| (job boards: actuarylist.com / LinkedIn "actuarial analyst") | official_job_posting | Volatile + login-gated; sample per run |

## Enrichment expectations

Expect `reinsurance`, `reserving`, `ratemaking`, `generalized linear
models`, `sas`, `excel` to count well. The wave-3 caveat applies in
full: exam-career vocabulary is proper-noun blueprint language, so
lexical enrichment is structurally weaker than for tech tracks — a
syllabus says "Univariate Random Variables," not "probability" per se.
Expect zero-support flags for `vba`, `pensions`, `statutory reporting`
(official PDFs phrase these differently); keep them — résumé-resolution
value stands on its own. Treat `sas`/`erm`/`alm`/`glm` counts as
advisory (short tokens).

## Overlap with existing tracks

Shares the stats core (`statistics`, `probability`, `regression`,
`hypothesis-testing`, `r`, `python`, `sql`, `excel`) with
`data_analyst`/`data_scientist` but nothing else — no DS&A, no system
design, no BI casework. `skill.glm`, `skill.sas`,
`skill.predictive-analytics` are natural data_scientist secondary tags.
A future quant/CFA-class track overlaps on `stochastic-processes`,
`asset-liability-management`, and the unclaimed `derivatives`/`fixed
income` tokens. The parallel insurance_agent draft is the heavy domain
neighbor: product vocabulary (`annuities`, `life insurance`,
`underwriting`) needs a single reconciliation pass across the two
profiles before either lands.
