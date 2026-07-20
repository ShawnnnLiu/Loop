# Real Estate Agent — Track Profile

**Proposed enum value:** `real_estate_agent` · **Wave 5** · Research grounded
2026-07-19.

## Track decision

Own track — a licensure career (wave 5, per `../03-wave-3-exam-careers.md`)
whose prep process is fully codified by exam vendors and state regulators,
and whose skill set is 100% disjoint from every tech track shipped so far
(zero existing taxonomy entries apply). Salesperson and broker are two
license tiers of the same pipeline (brokers need salesperson experience
first); one track covers both, anchored on the entry salesperson license.

**State-by-state variance IS the blueprint-version problem for this
career.** There is no single national license: each of the 50 states sets
its own pre-licensing course hours (observed span roughly 40–180: MI 40,
FL 63, NY 77, CA 135, TX 180 —
https://realestateu.com/faqs/real-estate-license/salesperson-pre-license/how-long-is-a-real-estate-course/),
contracts its own exam vendor (PSI for ~29 states, Pearson VUE for ~12,
plus state-run outliers —
https://www.psiexams.com/licensure/real-estate/), and appends its own
state-law portion to the shared national portion. Where wave-3 careers
have temporal blueprint versions (2023 vs 2026 NCLEX), this career has
**version × jurisdiction**: the Pearson VUE national outline is stamped
"Effective: January 2025 or later — check your state's content outlines
for implementation dates", i.e. even the shared blueprint rolls out
per-state. Plan/corpus contracts should treat "which state" the way exam
careers treat "which blueprint revision" — a required plan-level input,
not a skill.

**Resolver markers:** `"real estate agent"`, `"real estate salesperson"`,
`"real estate sales agent"`, `"realtor"`, `"real estate broker"`,
`"real estate license"`, `"licensed real estate"`. No collisions with the
thirteen existing tech tracks (none key on "agent", "broker", or "estate";
`skill.ai-agents` is a taxonomy entry, not a marker). Precedence hazards
are all future: keep every marker qualified with "real estate" — bare
`"agent"` would collide with insurance-agent titles, bare `"broker"` with
mortgage-broker/stockbroker titles, if those careers land later.
`"realtor"` is safe and heavily used as a self-description (it is NAR's
trademark for members, but candidates type it as the role name).

## Role snapshot

Licensed intermediary who represents buyers/sellers in property
transactions: prospecting and listing presentations, pricing via
comparative market analysis, MLS listing, showings/open houses, offer
negotiation, and shepherding contracts through financing contingencies to
closing. BLS projects **3% growth 2024–34 and ~46,300 openings/year**
across brokers and sales agents; median wage May 2024 was **$56,320 for
sales agents, $72,280 for brokers**; typical entry is a high-school
diploma plus state licensure
(https://www.bls.gov/ooh/sales/real-estate-brokers-and-sales-agents.htm).
One of the highest-churn licensure careers: commission-only income and low
entry barriers produce constant new-licensee inflow, so the "prep to
license" funnel is perennially large.

## Prep-process profile

- **Exam pipeline (not an interview loop):** pick state → complete the
  state-mandated pre-licensing course hours (40–180 by state; e.g. TX =
  180 hrs in six 30-hr courses —
  https://www.trec.texas.gov/become-licensed/sales-agent; CA = 135 hrs in
  three 45-hr courses; FL = 63 hrs; NY = 77 hrs; MI = 40 hrs) → file
  application + fingerprints/background check → sit the vendor exam (PSI
  or Pearson VUE by state). The exam is two scored portions: **national**
  (Pearson VUE: 80 scored + 5 unscored pretest items, outline effective
  Jan 2025 —
  https://www.pearsonvue.com/content/dam/VUE/vue/en/documents/publications/099913.pdf)
  and **state** (~30–50 items on state license law and commission rules).
  Passing is typically ~70–75% scaled (FL requires 70% —
  https://www.mlscampus.com/florida/sales-associate-pre-license/). Then
  activate under a sponsoring broker; most agents also join NAR and their
  local MLS to practice.
- **Credential-prerequisite gates (taxonomy can't model these as
  skills):** minimum age (18–19 by state); HS diploma/equivalent in many
  states; **course-hours completion certificate** — a hard scheduling
  gate with a known quantum, the wave-5 analog of PMP's 35 contact hours;
  fingerprint/background clearance (TREC issues license only after DPS
  check); **broker sponsorship** — the license is issued *inactive* until
  a sponsoring broker activates it (TREC model), the one gate that is a
  networking task, not study; post-license education deadlines in several
  states. The Planner must refuse to schedule the exam ahead of the
  course-hours gate rather than treat missing hours as a weak spot.
- **National blueprint weights (Pearson VUE salesperson, 80 scored
  items):** Contracts & Agency 16 · Property Value & Appraisal 11 · Real
  Property Characteristics/Legal Descriptions/Property Use 11 · Real
  Estate Practice (brokerage, fair housing, risk mgmt) 10 · Ownership/
  Transfer/Recording of Title 9 · Disclosures & Environmental Issues 9 ·
  Financing & Settlement 7 · Real Estate Math 7. Item counts make
  proportional coverage validation exact, the wave-3/5 sweet spot.
- **Anchor resources:** the vendor outlines themselves (Pearson VUE PDF
  above; PSI real-estate exam hub —
  https://www.psiexams.com/licensure/real-estate/); state commission
  candidate pages (TREC/DRE/DOS/DBPR); ARELLO's regulator directory for
  "which state, which rules" (https://www.arello.org/); NAR Code of
  Ethics for the post-license professional layer
  (https://www.nar.realtor/about-nar/governing-documents/code-of-ethics).
- **Typical arc (course-hours dominated):** state hours at self-paced
  online cadence over 4–12 weeks → 1–3 weeks of national-outline drilling
  weighted by item counts + state-portion law review → exam → sponsorship
  search running in parallel from mid-course. End-to-end commonly 2–6
  months, almost entirely a function of the state's hour requirement.

## Seed skill entries (draft)

### Existing entries — add `real_estate_agent` tag

**None.** The 166-entry v1 taxonomy is entirely software-flavored; no
existing entry or alias applies. This is the first fully disjoint track —
a useful stress test that union-fallback dilution (mechanics doc §C) now
spans genuinely unrelated vocabularies. (`skill.networking` exists but
means computer networks; real-estate "networking" must NOT tag it — see
collision notes.)

### New entries

Kind skew is expected and correct for a wave-5 career (03 doc, strain
#4): **13 concept, 3 practice, 1 tool, 0 language, 0 framework.** Do not
add validation that assumes kind balance. Entry names track the national
outline's domain structure so coverage maps 1:1 to blueprint weights.

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.real-property-concepts` | Real Property & Land Use | `real property`, `legal descriptions`, `land use controls`, `zoning`, `easements`, `encumbrances` | concept | real_estate_agent | Outline domain I (11 items) |
| `skill.ownership-title` | Ownership, Title & Deeds | `forms of ownership`, `title and deeds`, `deeds`, `title transfer`, `chain of title`, `title insurance` | concept | real_estate_agent | Domain II (9 items) |
| `skill.property-valuation` | Property Valuation & Appraisal Basics | `property valuation`, `appraisal`, `appraisal basics`, `comparative market analysis`, `cma`, `sales comparison approach`, `broker price opinion`, `bpo` | concept | real_estate_agent | Domain III (11 items); future appraiser track would tag this (shared candidate) |
| `skill.real-estate-contracts` | Real Estate Contracts | `real estate contracts`, `purchase agreements`, `sales contracts`, `offer and counteroffer`, `contingencies`, `earnest money` | concept | real_estate_agent | Half of domain IV (16 items). Bare `contracts` deliberately NOT claimed — see collision notes |
| `skill.agency-relationships` | Agency & Fiduciary Duties | `agency relationships`, `law of agency`, `fiduciary duties`, `dual agency`, `buyer representation`, `seller representation` | concept | real_estate_agent | Other half of domain IV |
| `skill.listing-agreements` | Listing Agreements | `listing agreements`, `exclusive right to sell`, `open listing`, `listing presentation` | concept | real_estate_agent | Domain V.B; also the core seller-side work product |
| `skill.fair-housing` | Fair Housing Law | `fair housing`, `fair housing act`, `fair housing laws`, `protected classes`, `equal housing opportunity` | concept | real_estate_agent | Domain V.C (3–4 items); heaviest-tested single law |
| `skill.real-estate-financing` | Real Estate Finance & Mortgages | `real estate finance`, `mortgage financing`, `mortgages`, `loan types`, `fha loans`, `va loans`, `conventional loans`, `private mortgage insurance` | concept | real_estate_agent | Domain VII; `mortgages` is contested if a loan-officer track lands — see notes |
| `skill.closing-escrow` | Closing, Escrow & Settlement | `closing process`, `escrow`, `settlement procedures`, `closing costs`, `closing disclosure`, `respa`, `trid` | concept | real_estate_agent | Domain VII.C–D; bare `closing` deliberately NOT claimed (FTS noise + sales-career collision) |
| `skill.property-disclosures` | Property Disclosures & Environmental Issues | `property disclosures`, `seller disclosure`, `environmental hazards`, `lead-based paint`, `material defects` | concept | real_estate_agent | Domain VI (9 items) |
| `skill.real-estate-math` | Real Estate Math | `real estate math`, `prorations`, `commission calculations`, `capitalization rate`, `cap rate` | concept | real_estate_agent | Domain VIII (7 items); pure drill material |
| `skill.license-law` | State License Law & Regulations | `real estate license law`, `license law`, `state license law`, `commission rules` | concept | real_estate_agent | The entire state portion (~30–50 items) hangs off this one entry — corpus must carry per-state docs |
| `skill.realtor-ethics` | REALTOR Code of Ethics | `nar code of ethics`, `realtor code of ethics` | concept | real_estate_agent | NAR-membership layer, not on the exam; `code of ethics` bare left contested |
| `skill.mls` | MLS | `mls`, `multiple listing service` | tool | real_estate_agent | Distinctive token; one of only two tool-kind entries the track has |
| `skill.real-estate-marketing` | Listing Marketing & Showings | `real estate marketing`, `property marketing`, `open houses`, `showings`, `staging` | practice | real_estate_agent | Post-license practice; bare `marketing` deliberately NOT claimed |
| `skill.negotiation` | Negotiation | `negotiation`, `negotiation skills` | practice | real_estate_agent, insurance_agent(2°), financial_advisor(2°) | NEW·shared (ruled 2026-07-19): defined here; the other sales tracks add-tag. HR keeps only long forms (`offer negotiation`, `salary negotiation`) on its offer-management entry |

Ruled 2026-07-19: the lead-generation entry this profile drafted was
FOLDED into `skill.prospecting` (defined in financial-advisor.md, shared
FAdv+IA+REA — owns `prospecting`, `lead generation`, `lead gen`,
`cold calling`, `client acquisition`, `sphere of influence`); this track
add-tags it, plus `skill.client-management` (management-consultant.md,
2°), `skill.consultative-selling` (insurance-agent.md, 2°), and
`skill.exam-simulation` (financial-advisor.md — the universal
exam-practice entry).

Track total: **16 new + ~4 shared add-tags ≈ 20** — far under the ~55 target and
the ~100 budget; correct for a licensure career whose blueprint has 8
domains, not 40 tools.

**Optional / deferred** (add only on enrichment/user demand): CRM tooling
(`crm` is contested across every sales-flavored career — do not claim
unilaterally), e-signature tools (`docusign`, `dotloop`, `zipform`),
property management basics (belongs to a future property-manager track),
real estate investing concepts (`noi`, `1031 exchange`), transaction
coordination, social-media marketing, broker-license upgrade topics.

## Alias-collision & FTS5 notes

- **`contracts` (bare) — do not claim.** Ambiguous across careers
  (paralegal/attorney, procurement, any engineering SOW context) and pure
  FTS noise in prose. `real estate contracts` is the trusted alias;
  résumé surfaces saying just "contracts" stay unresolved by design.
- **`networking` — already homed** on v1 `skill.networking` (computer
  networks, aliases `networking`/`computer networks`). Real-estate
  professional networking must not tag or claim it; `sphere of influence`
  (the industry's own term) carries that meaning on
  `skill.lead-generation`.
- **`prospecting`, `lead generation`, `cold calling` — RULED
  2026-07-19** onto the shared `skill.prospecting` (financial-advisor.md,
  FAdv+IA+REA); `sphere of influence` moved there too. This track tags
  the entry.
- **`negotiation` — RULED 2026-07-19:** defined here as NEW·shared
  (REA + IA/FAdv 2° tags).
- **`mortgages`, `real estate finance` — flag for a future
  loan-officer/mortgage (NMLS SAFE exam) track**, which would either
  co-tag `skill.real-estate-financing` or force a split. `closing` (bare)
  and `risk management` are NOT claimed: `closing` collides with sales
  prose ("closing deals") and `risk management` is effectively reserved
  by the PMP/PMI vocabulary (03 doc names it verbatim).
- **Short/noisy FTS tokens:** `mls` is distinctive in a real-estate
  corpus (safe); `cma` and `bpo` are noisy in general prose — trust
  `comparative market analysis` / `broker price opinion` counts. `cap
  rate` reads clean; bare `noi`/`ltv` deliberately left off. `hud`,
  `nar`, `fsbo` left off as org-name/abbrev noise; long forms cover them.
- **Blueprint-version mapping beats aliasing** (03 doc, strain #2): exam
  domains are canonical headings, so lexical alias variation is low, but
  entries must survive outline revisions (Jan-2025 outline rolled out
  per-state on different dates) — the append-only taxonomy versioning
  plus "supersedes" mapping is the mechanism, and here it must also carry
  the per-state dimension (`license law` content differs by state even at
  a fixed national revision).

## Candidate corpus sources (manifest seeds)

Manifest rule for licensure careers: official blueprints + government
pages + free explainers only. **Never ingest commercial prep material**
(Kaplan/Colibri/The CE Shop/CompuCram/PrepAgent question banks — the
UWorld/Becker class of this career).

| URL | expected type | note |
|---|---|---|
| https://www.pearsonvue.com/content/dam/VUE/vue/en/documents/publications/099913.pdf | role_taxonomy | Official national salesperson outline w/ per-domain item counts; effective Jan 2025, per-state rollout; PDF, stable between revisions |
| https://www.psiexams.com/licensure/real-estate/ | role_taxonomy | PSI real-estate exam hub (ARELLO-accredited); gateway to per-state candidate bulletins |
| https://www.bls.gov/ooh/sales/real-estate-brokers-and-sales-agents.htm | role_taxonomy | BLS OOH; public domain; NOTE: 403s non-browser user agents — ingestion needs a UA header |
| https://www.trec.texas.gov/become-licensed/sales-agent | role_taxonomy | TX: 180 qualifying hours, fingerprints, inactive-until-sponsored model; state gov, stable |
| https://www.dre.ca.gov/examinees/requirementssales.html | role_taxonomy | CA DRE: 135 hrs / three 45-hr courses; state gov, occasional URL churn |
| https://dos.ny.gov/real-estate-salesperson | role_taxonomy | NY DOS: 77-hr requirement + exam info; state gov |
| https://www2.myfloridalicense.com/real-estate-commission/ | role_taxonomy | FL DBPR/FREC: 63-hr course, 70% pass mark; myfloridalicense URLs churn — re-verify at ingest |
| https://www.arello.org/ | role_taxonomy | Regulator association; per-state agency directory + license-verification DB — the canonical "which state, which rules" index |
| https://www.nar.realtor/about-nar/governing-documents/code-of-ethics | role_taxonomy | NAR Code of Ethics (published free, NAR copyright — link/ingest text with license_note) |
| https://www.hud.gov/program_offices/fair_housing_equal_opp/fair_housing_act_overview | role_taxonomy | Fair Housing Act overview; federal public domain, very stable |
| https://www.consumerfinance.gov/owning-a-home/closing-disclosure/ | role_taxonomy | CFPB TRID/Closing Disclosure explainers; federal public domain |
| https://www.investopedia.com/articles/professionaleducation/10/six-steps-becoming-real-estate-agent.asp | role_taxonomy | Free end-to-end pipeline explainer; refreshed yearly; commercial site, text not redistributable |
| https://www.trec.texas.gov/agency-information/education-provider-exam-pass-rates | interview_report | Pass-rate statistics by education provider — the licensure analog of interview reports (03 doc, strain #5) |
| https://arec.alabama.gov/docs/forms/edu/pearson_national_general_salesperson_outline.pdf | role_taxonomy | Same national outline as republished by a state regulator — cross-check for per-state effective dates |
| (job boards: indeed/linkedin "real estate agent" + brokerage recruiting pages) | official_job_posting | Volatile, 45-day decay; sample per run; note most "postings" are brokerage recruiting funnels, not salaried openings |

## Enrichment expectations

Expect `mls`, `fair housing`, `escrow`, `appraisal`, `real estate
contracts`, `lead generation`, and `open houses` to dominate counts —
the corpus is blueprints + regulator pages, which use exactly these
headings. Zero-support flags likely for `realtor code of ethics`
(single-source), `sphere of influence`, and `staging` (marketing prose
varies) — keep them; résumé-resolution value stands. `cma`/`bpo`
per-alias counts will run hot in exam-adjacent prose — read the long
aliases as the signal. Because the corpus is state-fanned, per-track
counts for `license law` should be interpreted per-document, not summed
as if one blueprint.

## Overlap with existing tracks

**Zero entry overlap with all thirteen existing tracks** — no shared
skills, no shared aliases (nearest miss is `networking`, which is a
false friend, not an overlap). Prospective overlaps are all with unlanded
careers: insurance agent / financial advisor (prospecting, cold calling,
CRM, negotiation), loan officer (financing/mortgages, TRID/RESPA),
property manager (property management, leases), appraiser (valuation).
Reconciliation should treat this profile as the anchor claimant for
transaction-side vocabulary (`escrow`, `title`, `mls`) and a co-claimant,
not owner, of generic sales vocabulary.
