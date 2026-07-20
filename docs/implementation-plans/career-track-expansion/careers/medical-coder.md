# Medical Coder — Track Profile

**Proposed enum value:** `medical_coder` · **Wave 5** · Research grounded
2026-07-19.

## Track decision

Own track — an exam/licensure-driven career (wave-5 shape, see
`../03-wave-3-exam-careers.md`) with two governing bodies publishing
official, versioned, weighted blueprints: AAPC's CPC (100 questions,
4 hours, 17 knowledge areas —
https://www.aapc.com/certifications/cpc/taking-the-cpc-exam) and AHIMA's
CCS (5 domains with published weight ranges —
https://www.ahima.org/media/ecklaulp/css-exam-content-outline-1-1.pdf).
The skill list is almost totally disjoint from every existing track (zero
overlap with the 166-entry v1 taxonomy) and the prep process is
standardized online-course + codebook + timed-mock drilling — one of the
largest online career-course markets, and heavily remote-friendly.

**Resolver markers:** `"medical coder"`, `"medical coding"`,
`"medical biller"`, `"medical billing"`, `"billing and coding"`,
`"medical billing and coding"`, `"certified professional coder"`,
`"coding specialist"`, `"medical records specialist"`,
`"health information technician"`, `"inpatient coder"`,
`"outpatient coder"`, `"risk adjustment coder"`.

Precedence hazards: never use bare `"coder"` or `"coding"` — they appear
inside normalized software-role strings ("coding bootcamp grad seeking
swe"). `"coding specialist"` should be inserted **before** any
swe-adjacent fallback marker so it cannot leak to `swe`. `"cpc"` is NOT a
marker (cost-per-click collision in marketing roles). No collisions
expected with mle/ai_engineer/data tracks.

## Role snapshot

Translates provider documentation in the health record into standardized
ICD-10-CM diagnosis codes and CPT/HCPCS procedure codes for claims and
reimbursement; the certification-gated core of the healthcare revenue
cycle. BLS "Medical Records Specialists" (the OOH occupation containing
coders): median pay $50,250 (May 2024), +7% projected growth 2024–34
("much faster than average"), ~14,200 openings/yr, 194,800 jobs held in
2024
(https://www.bls.gov/ooh/healthcare/medical-records-and-health-information-technicians.htm).
AAPC reports 300,000+ members and bills itself the largest
training/credentialing organization for the business of healthcare
(https://www.aapc.com/memberships/). Certification is effectively
mandatory for hiring; a large share of coding jobs are remote.

## Prep-process profile

- **Exam pipeline (not an interview loop):** choose credential (CPC =
  AAPC, physician/outpatient; CCS = AHIMA, hospital/inpatient; CCA =
  AHIMA entry level) → join AAPC (membership is **required** to sit the
  CPC; ~$229–$299/yr, student ~$164) → prep course (AAPC's own, a
  community-college certificate, or self-study) → schedule exam (online
  proctored or in-person; not window-locked like bar/CFA) → pass at
  70/100 (CPC) → **CPC-A apprentice designation** until the experience
  gate clears (see below) → optional specialty credentials (CRC risk
  adjustment, COC outpatient, CIC inpatient).
  CPC: 100 MCQs, 4 hrs, open-book with exactly three approved codebooks
  (AMA CPT Professional, ICD-10-CM, any HCPCS Level II); ~$425/attempt
  (https://www.aapc.com/certifications/cpc/taking-the-cpc-exam,
  structure corroborated at
  https://www.mometrix.com/academy/cpc-practice-test/). CPC knowledge
  areas: the six CPT body-system series (10000–60000, 6 Qs each), E/M,
  anesthesia, radiology, laboratory/pathology, medicine, medical
  terminology, anatomy, ICD-10-CM, HCPCS Level II, coding guidelines,
  compliance/regulatory, plus 10 case questions.
  CCS: 5 weighted domains — Coding Knowledge & Skills 39–41%, Coding
  Documentation 18–22%, Provider Queries 9–11%, Regulatory Compliance
  18–22%, Information Technologies 9–11%; scenarios split evenly
  inpatient/outpatient/ED (official outline, effective 05/01/2024:
  https://www.ahima.org/media/ecklaulp/css-exam-content-outline-1-1.pdf).
  Published weights make proportional coverage validation exact — the
  wave-3 pattern.
- **Credential-prereq gates (taxonomy cannot model these as skills):**
  (1) AAPC membership to register; (2) CPC-A → CPC removal requires two
  years of coding experience (education/practicum pathways can
  substitute for part of it); (3) AHIMA recommends but does not require
  coding coursework/experience for CCS. No degree is legally required —
  BLS: postsecondary certificate typical. The Planner must treat the
  membership + experience gates as prerequisite facts, not weak spots.
- **Blueprint/version mapping (the code-set version problem):** code
  sets themselves revise annually on fixed dates — ICD-10-CM every
  **October 1** (FY2026: 487 additions, 28 deletions, 38 revisions;
  https://www.cms.gov/medicare/coding-billing/icd-10-codes, guidelines
  PDF: https://www.cms.gov/files/document/fy-2026-icd-10-cm-coding-guidelines.pdf)
  and CPT every **January 1** (2026 set: 288 new / 84 deleted / 46
  revised;
  https://www.ama-assn.org/press-center/ama-press-releases/ama-releases-cpt-2026-code-set).
  Exams re-pin to the new codebooks on announced dates (CCS requires
  2026 codebooks for all exams on/after 05/01/2026). Studying against
  last year's codebook is the canonical failure mode — a literal
  blueprint-version/temporal-aliasing case for the append-only taxonomy
  versioning.
- **Anchor resources:** AAPC CPC page + Official CPC Study Guide
  (https://www.aapc.com/certifications/cpc); AHIMA CCS overview
  (https://www.ahima.org/certification-careers/certifications-overview/ccs/);
  CMS ICD-10 hub and official coding guidelines (free, public domain);
  free practice-exam explainers (Mometrix, Pocket Prep). Commercial prep
  courseware (AAPC paid courses, Career Step, UWorld-class banks) is
  copyrighted — never ingest (wave-3 corpus rule).
- **Typical 16-week arc:** medical terminology + anatomy & physiology →
  ICD-10-CM conventions and Official Guidelines → CPT by body-system
  series + E/M leveling + modifiers → HCPCS Level II, compliance
  (HIPAA/NCCI/medical necessity) + revenue-cycle context → timed
  full-length mocks with codebook tabbing/navigation drills (the
  open-book exam is a time-management exam).

## Seed skill entries (draft)

### Existing entries — add `medical_coder` tag

Nothing in taxonomy v1 applies — the track is fully disjoint from tech
(verified against all 166 v1 entries). One NEW·shared registry entry
applies: `skill.compliance` (defined in `cloud-engineer.md`, tracks
CE/SA) gains a `medical_coder` tag. Ruled 2026-07-19: the `hipaa` alias
moved off that entry onto this profile's `skill.hipaa-privacy` (see
collision notes). Also tagged: `skill.exam-simulation`
(financial-advisor.md — the universal exam-practice entry).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.icd-10-cm` | ICD-10-CM Diagnosis Coding | `icd-10-cm`, `icd 10 cm`, `icd-10`, `icd 10`, `diagnosis coding` | concept | medical_coder | Core code set; annual Oct 1 revision — version-pin hazard |
| `skill.icd-10-pcs` | ICD-10-PCS Procedure Coding | `icd-10-pcs`, `icd 10 pcs`, `inpatient procedure coding` | concept | medical_coder | CCS/inpatient side |
| `skill.cpt-coding` | CPT Coding | `cpt`, `cpt coding`, `current procedural terminology`, `procedure coding` | concept | medical_coder | Annual Jan 1 revision; AMA-copyrighted content |
| `skill.hcpcs` | HCPCS Level II | `hcpcs`, `hcpcs level ii`, `hcpcs level 2` | concept | medical_coder | Supplies, drugs, DME |
| `skill.em-coding` | E/M Coding | `e/m coding`, `em coding`, `evaluation and management` | concept | medical_coder | Highest-stakes CPT area; `e/m` bare deferred (noisy) |
| `skill.coding-modifiers` | CPT/HCPCS Modifiers | `modifiers`, `coding modifiers`, `modifier 25`, `modifier 59` | concept | medical_coder | `modifiers` collides with "access modifiers" in tech prose — FTS noise, see notes |
| `skill.coding-guidelines` | Official Coding Guidelines | `coding guidelines`, `coding conventions`, `official guidelines for coding and reporting` | concept | medical_coder | ICD-10-CM Official Guidelines; `coding guidelines` noisy in tech corpus |
| `skill.medical-terminology` | Medical Terminology | `medical terminology`, `medical vocabulary` | concept | medical_coder | Shared-candidate with any future nursing/clinical track |
| `skill.anatomy-physiology` | Anatomy & Physiology | `anatomy and physiology`, `anatomy & physiology`, `a&p`, `human anatomy`, `physiology` | concept | medical_coder | Bare `anatomy` deliberately NOT claimed (prose noise: "loop anatomy"); shared-candidate with nursing |
| `skill.medical-billing` | Medical Billing | `medical billing`, `billing and coding`, `claims submission`, `claims processing` | practice | medical_coder | The biller half of biller/coder hybrid roles |
| `skill.revenue-cycle` | Revenue Cycle Management | `revenue cycle`, `revenue cycle management`, `rcm` | concept | medical_coder | `rcm` short token — trust long aliases |
| `skill.reimbursement` | Reimbursement Methodologies | `reimbursement`, `reimbursement methodologies`, `drg`, `ms-drg`, `apc` | concept | medical_coder | CCS Domain 1 task; DRG/APC grouping |
| `skill.denials-management` | Denials & Appeals | `denials management`, `claim denials`, `claim appeals` | practice | medical_coder | Bare `appeals` too generic — not claimed |
| `skill.hipaa-privacy` | HIPAA & PHI | `hipaa`, `hipaa compliance`, `protected health information`, `phi` | concept | medical_coder | Ruled 2026-07-19: bare `hipaa` re-homed here from `skill.compliance` (cloud-engineer.md keeps the framework aliases); `phi` short/noisy, `pii` deliberately homeless — never alias it |
| `skill.medical-necessity` | Medical Necessity & Coding Edits | `medical necessity`, `ncci`, `ncci edits` | concept | medical_coder | NCCI/payer edits; `lcd`/`ncd` bare deliberately not claimed (display-tech collision) |
| `skill.medicare-payer-rules` | Medicare & Payer Guidelines | `medicare`, `medicaid`, `payer guidelines`, `cms guidelines` | concept | medical_coder | Compliance/regulatory knowledge area on both exams |
| `skill.ehr-systems` | EHR Systems | `electronic health records`, `electronic health record`, `electronic medical records`, `ehr`, `emr`, `epic ehr`, `epic systems`, `cerner` | tool | medical_coder | Bare `epic` NEVER (agile epics); splitting Epic/Cerner into own entries is a curation call; `ehr`/`emr` short-token noise |
| `skill.encoder-software` | Encoder Software | `medical coding encoder`, `3m encoder`, `encoderpro`, `trucode` | tool | medical_coder | Bare `encoder` NEVER — ML transformer collision; the track's only real tooling besides EHR + codebooks |
| `skill.medical-auditing` | Coding Audits | `medical auditing`, `coding audits`, `chart audits` | practice | medical_coder | Post-credential growth path (CPMA); appears in senior postings |
| `skill.cdi` | Clinical Documentation Integrity | `clinical documentation improvement`, `clinical documentation integrity`, `cdi`, `provider queries`, `physician queries` | concept | medical_coder | CCS Domain 3 (Provider Queries, 9–11%); `cdi` short token |

**Optional / deferred** (protect the budget; add on enrichment or user
demand): pathophysiology and pharmacology basics (better homed on a
future nursing track — shared-candidates), chart abstraction as its own
entry (currently implied by auditing/CDI), computer-assisted coding
(CAC), risk-adjustment/HCC coding (CRC credential), place-of-service
codes, UB-04/CMS-1500 claim forms. (The shared exam-drilling practice
entry was ruled 2026-07-19: `skill.exam-simulation`, defined in
financial-advisor.md — this track tags it.)

Track total: 20 new + 1 shared tag ≈ 21 — far under the ~55 target and
the ~100 prompt budget. Kind skew is the expected wave-3 shape: concept
15 / practice 3 / tool 2 / language 0 / framework 0. Do not add
validation assuming kind balance.

## Alias-collision & FTS5 notes

- **`coding` bare is CATASTROPHICALLY ambiguous** with every software
  track (v1 `skill.application-security` already carries
  `secure coding`) — never an alias, never a resolver marker. All
  aliases here use `medical coding`, `cpt coding`, `diagnosis coding`,
  etc.
- **`hipaa` — RULED 2026-07-19.** Re-homed from `skill.compliance`
  (cloud-engineer.md, which keeps `compliance`/`pci dss`/`soc 2`/
  `fedramp`/`grc` and gains a `medical_coder` tag) onto
  `skill.hipaa-privacy` here: for a medical coder HIPAA is a core exam
  domain, not a compliance-framework flavor. Per the registry protocol,
  cloud-engineer.md was updated in the same pass.
- **`encoder` bare — never.** Collides head-on with transformer
  encoder/decoder prose across mle/ai_engineer corpora. Long forms only
  (`3m encoder`, `encoderpro`).
- **`epic` bare — never** (agile epics in PM/mobile corpora). `epic ehr`
  / `epic systems` only.
- **`modifiers` and `coding guidelines`** are claimed but FTS-noisy
  ("access modifiers", tech style guides). Trust `modifier 25`,
  `official guidelines for coding and reporting` counts; treat bare-form
  counts as advisory (per-alias counts disambiguate).
- **Short/noisy tokens flagged:** `ehr`, `emr`, `cdi`, `rcm`, `phi`,
  `a&p`, `cpt`, `hcpcs` (the last two are distinctive in a healthcare
  corpus but near-absent elsewhere — cross-track counts should be ~0).
  Long aliases are the trustworthy enrichment signal in every case.
- **Deliberately homeless respected:** `pii` never aliased (`phi` is the
  healthcare term and stays on `skill.hipaa-privacy` if it survives
  review); bare `anatomy`, `appeals`, `lcd`, `ncd`, `e/m` not claimed.
- **Shared-candidates with future clinical tracks:** `medical
  terminology`, `anatomy and physiology`, `ehr`/`emr`, `hipaa
  compliance` will all be wanted by a registered-nurse (NCLEX) track if
  one lands. Create once here (or wherever lands first), tag both — the
  02-registry pattern.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/healthcare/medical-records-and-health-information-technicians.htm | role_taxonomy | BLS OOH; public domain, stable, annual refresh |
| https://www.aapc.com/certifications/cpc | role_taxonomy | Official CPC scope; JS-heavy page — may need rendered fetch |
| https://www.aapc.com/certifications/cpc/taking-the-cpc-exam | role_taxonomy | Official exam structure, knowledge areas, codebook rules |
| https://www.aapc.com/certifications/cpc-and-cpb/taking-the-cpc-and-cpb-exams | role_taxonomy | CPC+CPB logistics, membership requirement |
| https://www.ahima.org/media/ecklaulp/css-exam-content-outline-1-1.pdf | role_taxonomy | Official CCS outline with domain weights; stable PDF, effective 05/01/2024 |
| https://www.ahima.org/certification-careers/certifications-overview/ccs/ | role_taxonomy | Official CCS overview + eligibility |
| https://www.ahima.org/certification-careers/certifications-overview/cca/ | role_taxonomy | Entry-level CCA credential scope |
| https://www.cms.gov/medicare/coding-billing/icd-10-codes | role_taxonomy | Official ICD-10 hub; public domain; annual churn by design (Oct 1) |
| https://www.cms.gov/files/document/fy-2026-icd-10-cm-coding-guidelines.pdf | role_taxonomy | The Official Guidelines themselves; free, versioned yearly — re-pin each FY |
| https://www.cdc.gov/nchs/icd/icd-10-cm/index.html | role_taxonomy | NCHS ICD-10-CM files; public domain |
| https://www.ama-assn.org/press-center/ama-press-releases/ama-releases-cpt-2026-code-set | role_taxonomy | CPT 2026 release summary; CPT codebook content itself is AMA-copyrighted — never ingest the code set |
| https://www.mometrix.com/academy/cpc-practice-test/ | interview_report | Free exam-structure/area breakdown (exam-experience analog); commercial, moderately volatile |
| https://www.pocketprep.com/posts/learn-what-to-study-for-the-aapc-cpc-examination/ | interview_report | Free CPC study-scope explainer |
| (job boards: indeed/linkedin "medical coder" searches) | official_job_posting | Volatile + login-gated; sample per run |

License rule (wave-3 mirror): official blueprints + free explainers
only. CPT® content, AAPC/AHIMA paid courseware, and UWorld/Career-Step
class prep material are aggressively copyrighted — never ingest.

## Enrichment expectations

Expect `icd-10`, `cpt`, `medical billing`, `medical coding`,
`electronic health records`, `hipaa compliance`, `medicare`, `revenue
cycle` to dominate counts. Zero-support flags likely for `encoderpro`,
`trucode`, `modifier 59`, `claim appeals` (niche or paywalled prose) —
keep them; résumé-resolution value stands alone. Counts for `modifiers`,
`coding guidelines`, `physiology` will be inflated by cross-track prose
— read per-alias counts, not entry totals.

## Overlap with existing tracks

Effectively zero overlap with all nine tech tracks and v1 — the cleanest
disjoint track in the expansion (good enum-resolution property; its
entries cannot mis-resolve a tech résumé). Sole registry touchpoint:
`skill.compliance` (CE/SA) via HIPAA/regulatory overlap. Forward
overlap: a future registered-nurse or health-information track shares
terminology/A&P/EHR/HIPAA entries — the shared-candidate flags above are
for that reconciliation, not for any current profile.
