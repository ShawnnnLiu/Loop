# Electrician (Apprenticeship → Journeyman License) — Track Profile

**Proposed enum value:** `electrician` · **Wave 5** · Research grounded
2026-07-19.

## Track decision

Own track — and the **proxy/template for skilled trades generally**
(plumber, HVAC tech, carpenter would clone this shape). The prep process
is fully codified but shares zero machinery with any tech track: an
entrance aptitude test (algebra + reading), then a multi-year
apprenticeship, then an NEC-code-based journeyman licensing exam.

**Honesty about product fit (this shaped the rank):** the multi-year
middle of this career is *employment*, not schedulable study — ~8,000
paid on-the-job hours plus employer/JATC-scheduled classroom instruction
(https://www.bls.gov/ooh/construction-and-extraction/electricians.htm).
The product can only schedule the two bookends: (1) the entrance
aptitude-test prep arc (weeks), and (2) the journeyman-exam prep arc
(~8–12 weeks) years later. Everything between is out of scope. The track
is still worth landing because both bookends are real, high-stakes,
blueprint-driven study phases — and because it proves the taxonomy can
model a non-desk trade at all.

This is also the first track with **zero overlap with the existing
taxonomy** (see below) — it exercises the "fully disjoint vocabulary"
path end-to-end.

**Resolver markers:** `"electrician"`, `"journeyman electrician"`,
`"apprentice electrician"`, `"electrician apprentice"`,
`"electrical apprenticeship"`, `"master electrician"`,
`"inside wireman"`, `"residential wireman"`. Precedence hazards: none of
the thirteen existing tracks (swe, mle, ai_engineer, quant_dev,
data_scientist, data_analyst, data_engineer, devops_sre, cloud_engineer,
security_analyst, product_manager, ux_designer, mobile_engineer) can
partially match these phrases. Do **not** add bare `"electrical"` as a
marker — "electrical engineer" is a different occupation and must fall
through to `None`. `"electrical technician"` is deliberately omitted
(often electronics repair, a different BLS occupation). Ordering vs
existing tracks is irrelevant; future trades tracks (hvac, plumber)
would need mutual precedence review.

## Role snapshot

Installs, maintains, and repairs electrical power, lighting, and control
systems in homes, businesses, and factories. Strong official outlook:
median pay **$62,350/yr** (May 2024), **~81,000 openings/yr** projected
on average over the decade, employment growing **9% (2024–34)**, "much
faster than average"
(https://www.bls.gov/ooh/construction-and-extraction/electricians.htm).
Typical entry is a 4–5 year registered apprenticeship: ~2,000 paid OJT
hours per year (~8,000 total) plus technical instruction in electrical
theory, blueprint reading, mathematics, electrical code requirements,
and safety/first-aid practices (same BLS page). Growth is driven partly
by construction and alternative-energy (solar/wind) buildout
(https://www.cnbc.com/2024/07/27/americas-demand-skilled-electricians-boom.html).

## Prep-process profile

This is an **exam pipeline**, not an interview loop, with an
employment-shaped middle:

- **Phase 1 — apprenticeship entrance (schedulable):** apply to an
  IBEW/NECA JATC (or non-union program) → **Electrical Training Alliance
  aptitude test**: 33 algebra & functions questions in 46 min + 36
  reading-comprehension questions in 51 min, multiple choice, no
  calculator; scored on a 1–9 stanine, most locals requiring ≥4 to reach
  the oral interview
  (https://www.iprep.online/courses/njatc-aptitude-test-free/,
  https://www.12minprep.com/knowledge-hub/ibew-aptitude-test/) → oral
  interview → ranked eligibility pool → acceptance (can take months —
  a hard gate, not a skill).
- **Phase 2 — apprenticeship (NOT schedulable study):** 4–5 years of
  paid on-the-job training (~8,000 hours) plus classroom instruction
  (commonly quoted 576–1,000 hours across programs), curriculum owned by
  the Electrical Training Alliance
  (http://www.electricaltrainingalliance.org/training/apprenticeshipTraining).
  The product must refuse to "plan" this phase.
- **Phase 3 — journeyman licensing exam (schedulable):** state-variant.
  Example: Texas requires 7,000 OJT hours to sit and 8,000 for the
  license; the exam is open-book against the NEC, administered by PSI
  (https://www.tdlr.texas.gov/electricians/elecexam.htm,
  https://www.tdlr.texas.gov/electricians/pdf/Candidate-Information-Bulletin.pdf).
  Typical shape across states: 80–100 questions, 4–5 hours, ~70–75%
  passing, content dominated by NEC application (~60–70%) plus
  electrical theory and load/voltage-drop calculations
  (https://www.voltagelab.com/nec-exam-prep-guide-2026-how-to-pass-the-journeyman-master-test/).
  **Which NEC edition applies is a per-state adoption question** — in
  2026 some boards still test on the 2023 NEC, others on the 2026
  (https://www.jadelearning.com/nec-code-adoptions-by-state/); Texas
  cuts over to the 2026 NEC on 2026-09-01
  (https://electricianprep.co/blog/nec-2023-vs-nec-2026-texas-exam-changes).
- **Anchor resources:** BLS OOH page; Electrical Training Alliance
  apprenticeship pages; local-union aptitude prep sheets (e.g.
  https://ibew99.org/sites/ibew99.org/files/aptitude_test_prep.pdf);
  state licensing-board candidate bulletins (content outlines with
  domain percentages); OSHA outreach training
  (https://www.osha.gov/training/outreach/construction); free NEC
  explainers (e.g. https://www.mikeholt.com/technical.php).
- **Typical week-arcs:** entrance phase = 4–8 weeks of algebra drills +
  timed reading practice + mock aptitude tests; journeyman phase = 8–12
  weeks allocating hours proportional to the state content outline —
  NEC chapter drills (grounding/bonding, conductors, motors), load and
  voltage-drop calculation sets, timed open-book code-navigation
  practice, full simulated exams.

### Credential-prerequisite gates (not modelable as skills)

Mirror of `03-wave-3-exam-careers.md` §1 — the Planner must refuse to
schedule around unmet gates rather than treat them as weak spots:

- high-school diploma/GED + typically one year of algebra to apply;
- **apprenticeship acceptance** (test + interview + ranked pool);
- **~8,000 OJT hours** and program classroom hours before exam
  eligibility (Texas: 7,000 to sit, 8,000 to license);
- **state variance**: some states license statewide, others delegate to
  municipalities; hour counts, exam vendors, reciprocity, and adopted
  NEC edition all vary
  (https://www.jcrproductions.com/pages/state-requirements-electricians).

### Blueprint/version mapping

The NEC revises on a fixed 3-year cycle (2020 → 2023 → 2026) and states
adopt on a lag — the same temporal-aliasing problem 03 records for
NCLEX/PMP/UBE. A journeyman-prep plan is pinned to the *state's adopted
edition*, not the newest one.

### Kind-distribution skew

`concept` + `practice` dominate; the only `tool` entries are physical
instruments; `language`/`framework` are empty and must stay empty. Do
not add validation assuming kind balance (03 §4). Near-zero software
tools is correct, not a gap.

## Seed skill entries (draft)

### Existing entries — add `electrician` tag

**None.** No v1 entry (nor any NEW·shared entry in
`../02-shared-entries.md`) applies — this is the first fully-disjoint
track. Consequence worth recording: every unresolved role's union
fallback now includes ~20 entries of trade vocabulary, which slightly
dilutes the fallback for tech users (the generous resolver markers above
are the mitigation).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.algebra-functions` | Algebra & Functions | `algebra`, `algebra and functions`, `number series`, `solving equations` | concept | electrician | Aptitude-test math section (33q/46min). `algebra` FTS-collides with prose about `linear algebra` (mle) — trust the long aliases |
| `skill.reading-comprehension` | Reading Comprehension | `reading comprehension` | concept | electrician | Aptitude-test reading section (36q/51min); likely shared with future trades/exam tracks |
| `skill.electrical-theory` | Electrical Theory | `electrical theory`, `ohm's law`, `ohms law`, `ac theory`, `dc theory`, `series and parallel circuits`, `electrical circuits` | concept | electrician | Foundation for both classroom and exam phases |
| `skill.three-phase-power` | Three-Phase Power | `three-phase power`, `three phase power`, `3-phase`, `single-phase` | concept | electrician | Commercial/industrial staple; distinctive FTS terms |
| `skill.electrical-calculations` | Electrical Calculations | `electrical calculations`, `load calculations`, `voltage drop`, `conductor sizing`, `box fill`, `conduit fill`, `service sizing` | concept | electrician | The exam workhorse (~10–20% of questions); highly distinctive corpus terms |
| `skill.conductors-ampacity` | Conductors & Ampacity | `ampacity`, `wire sizing`, `awg`, `conductors` | concept | electrician | NEC 310 tables; `awg` is a short FTS token — trust `ampacity` |
| `skill.national-electrical-code` | National Electrical Code | `national electrical code`, `nec`, `nec code`, `nfpa 70`, `electrical code`, `code book navigation` | concept | electrician | Exam center of gravity (~60–70%). `nec` is a short/noisy FTS token — trust `national electrical code` for enrichment |
| `skill.grounding-bonding` | Grounding & Bonding | `grounding and bonding`, `grounding`, `equipment grounding`, `grounding electrode` | concept | electrician | NEC Article 250 — top-weighted exam article. Bare `bonding` deliberately NOT an alias (too generic) |
| `skill.overcurrent-protection` | Overcurrent Protection | `overcurrent protection`, `circuit breakers`, `fuses`, `short-circuit protection` | concept | electrician | Breaker/fuse sizing questions |
| `skill.services-feeders` | Services, Feeders & Panels | `electrical services`, `service entrance`, `feeders`, `panelboards`, `load centers` | concept | electrician | Service-sizing scenario questions |
| `skill.electrical-transformers` | Transformers (Electrical) | `electrical transformers`, `transformer theory`, `transformer connections` | concept | electrician | Bare `transformers` is OWNED by `skill.transformers` (mle) — cannot claim; long aliases only |
| `skill.motor-controls` | Motors & Motor Controls | `motor controls`, `motor control`, `electric motors`, `motor starters`, `ladder diagrams`, `ladder logic` | concept | electrician | NEC 430 is ~exam-critical; ladder logic here, PLCs deferred |
| `skill.conduit-bending` | Conduit Bending & Raceways | `conduit bending`, `conduit`, `emt`, `raceways` | practice | electrician | Signature hands-on skill; `emt` is short AND collides with "emergency medical technician" in mixed corpora — trust `conduit bending` |
| `skill.wiring-methods` | Wiring Methods & Installation | `wiring methods`, `rough-in wiring`, `rough in`, `nm cable`, `romex`, `cable tray` | practice | electrician | NEC Chapter 3; posting language incl. brand-genericized `romex` |
| `skill.blueprint-reading` | Blueprint Reading | `blueprint reading`, `blueprints`, `electrical drawings`, `schematics`, `construction drawings` | concept | electrician | BLS-named classroom subject; likely shared with future trades tracks |
| `skill.electrical-troubleshooting` | Electrical Troubleshooting | `electrical troubleshooting`, `circuit troubleshooting` | practice | electrician | Bare `troubleshooting` is OWNED by `skill.troubleshooting` (cloud_engineer) — long forms only |
| `skill.test-instruments` | Electrical Test Instruments | `multimeter`, `test instruments`, `voltage tester`, `clamp meter`, `megger` | tool | electrician | The trade's "tool" entries are physical instruments |
| `skill.hand-power-tools` | Hand & Power Tools | `hand tools`, `power tools` | tool | electrician | Generic across all future trades — natural NEW·shared candidate when a second trade lands |
| `skill.electrical-safety` | Electrical Safety & Arc Flash | `electrical safety`, `arc flash`, `nfpa 70e`, `lockout tagout`, `lockout/tagout`, `loto` | practice | electrician | NFPA 70E is distinct from NEC; `loto` shared with future trades |
| `skill.osha-10` | OSHA 10 & Jobsite Safety | `osha 10`, `osha 30`, `osha`, `construction safety`, `jobsite safety` | practice | electrician | Common elective/requirement (https://www.osha.gov/training/outreach/construction); `osha` likely shared with every future trades track — see collisions |

Track total: **20 entries (all new, 0 existing)** — well under the ~55
target and the ~100 prompt budget.

**Optional / deferred** (add only if enrichment or user demand
supports): mechanical aptitude (`mechanical aptitude`, `mechanical
comprehension` — only some locals test it); PLC basics (`programmable
logic controllers`, `plc` — industrial specialization; `plc` is a short
FTS token); first aid & CPR (**contested** — a future
nursing/EMT/trades track is the better home for `cpr`/`first aid`);
solar PV installation (`solar installation`, `photovoltaic` — BLS-cited
growth area); low-voltage/fire-alarm systems; electrical estimating
(master-level, beyond journeyman scope).

## Alias-collision & FTS5 notes

- **`transformers` — do NOT claim.** Homed on `skill.transformers`
  (mle/ai_engineer, v1). This track uses `electrical transformers` /
  `transformer theory`. Résumé surfaces saying just "transformers" from
  an electrician résumé will mis-resolve to the ML entry — accepted
  limitation; the resolver's track context cannot help (aliases are
  global).
- **`troubleshooting` — do NOT claim.** Homed on `skill.troubleshooting`
  (cloud-engineer.md, NEW). This track uses `electrical
  troubleshooting`.
- **`nec`** — flagged short/noisy FTS token (also "NEC" the Japanese
  electronics company in mixed corpora). Kept as a résumé-resolution
  alias; enrichment must trust `national electrical code`.
- **`algebra`** — free as an exact alias (v1 has only `linear algebra`),
  but FTS5 token overlap means corpus prose about "linear algebra"
  inflates its count. Trust `algebra and functions`. CONTESTED in
  spirit: any future exam career with a math-aptitude gate may want it.
- **`osha`, `osha 10`, `hand tools`, `power tools`, `blueprint
  reading`, `lockout tagout`, `reading comprehension`** — free today,
  claimed here, but all are natural shared entries the moment any other
  trades track (hvac, plumber, welder) lands. Reconciliation should
  treat `skill.osha-10`, `skill.hand-power-tools`,
  `skill.blueprint-reading`, and `skill.reading-comprehension` as
  future NEW·shared rows with this profile as the defining home.
- **`emt`** — short token AND cross-domain ambiguous (electrical
  metallic tubing vs emergency medical technician). Kept for résumé
  resolution; worthless for enrichment counting — trust `conduit
  bending` / `raceways`.
- **`awg`, `loto`, `3-phase`** — short tokens; trust the long aliases
  (`ampacity`, `lockout tagout`, `three-phase power`).
- Bare `bonding`, `grounding`? — `grounding` claimed (domain-distinct
  in a trades corpus); bare `bonding` deliberately NOT an alias (too
  generic in English prose).
- Per the deliberately-homeless list in `../02-shared-entries.md`:
  nothing here claims `playbooks`, `documentation`, `star`, etc.
- Cross-exam-career hazard for reconciliation: generic exam-prep tokens
  (`practice exams`, `timed practice`, `test taking strategies`) are
  wanted by every wave-5 exam career — they should be ruled centrally
  (probably deliberately homeless or one shared entry), so this profile
  does not claim them.

## Candidate corpus sources (manifest seeds)

Manifest rule per 03: official blueprints + free explainers only —
**never ingest the NEC code text itself** (NFPA copyright; free-access
viewer is login-gated and non-scrapable) and no commercial prep
courseware (Mike Holt paid products, 1ExamPrep, JobTestPrep — the
UWorld/Kaplan class of this trade).

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/construction-and-extraction/electricians.htm | role_taxonomy | Official OOH page; stable; server 403s naive fetchers — ingest tool needs a browser UA |
| http://www.electricaltrainingalliance.org/training/apprenticeshipTraining | role_taxonomy | Official IBEW/NECA apprenticeship curriculum owner; stable; note http-only |
| https://ibew99.org/sites/ibew99.org/files/aptitude_test_prep.pdf | role_taxonomy | Official local-union aptitude prep sheet (algebra+reading scope); PDF; free |
| https://www.tdlr.texas.gov/electricians/elecexam.htm | role_taxonomy | Official state licensing/exam requirements (TX as exemplar state); stable |
| https://www.tdlr.texas.gov/electricians/pdf/Candidate-Information-Bulletin.pdf | role_taxonomy | Official PSI candidate bulletin with exam content outline; revised on NEC cutover dates |
| https://www.osha.gov/training/outreach/construction | role_taxonomy | Official OSHA 10/30 outreach program scope; public domain; stable |
| https://www.osha.gov/electrical | role_taxonomy | Official OSHA electrical-hazard standards page; public domain |
| https://www.nfpa.org/codes-and-standards/nfpa-70-standard-development/70 | role_taxonomy | NEC *about/edition* page only — code text itself must never be ingested (license) |
| https://www.jadelearning.com/nec-code-adoptions-by-state/ | role_taxonomy | Per-state NEC edition adoption map; commercial CE provider but free page; updated ~yearly |
| https://www.jcrproductions.com/pages/state-requirements-electricians | role_taxonomy | Per-state licensing/CE requirement roundup; free; moderate volatility |
| https://www.mikeholt.com/technical.php | role_taxonomy | Free NEC explainer library (free articles only — no paid courseware) |
| https://www.voltagelab.com/nec-exam-prep-guide-2026-how-to-pass-the-journeyman-master-test/ | interview_report | Exam-experience-shaped prep guide (format, article weights); refreshed per code cycle |
| https://www.12minprep.com/knowledge-hub/ibew-aptitude-test/ | interview_report | Aptitude-test structure/experience guide; free tier only |
| https://www.ultimateelectriciansguide.com/free-journeyman-electrician-practice-test/ | interview_report | Free journeyman practice questions; free tier only |
| (job boards: indeed/apprenticeship.gov "electrician apprentice" searches) | official_job_posting | Volatile (45-day prior); sample per run via https://www.apprenticeship.gov/apprenticeship-job-finder |

## Enrichment expectations

Expect `national electrical code`, `conduit`, `grounding`, `voltage
drop`, `load calculations`, `arc flash`, and `osha 10` to dominate
counts — the corpus is code-explainer-heavy by construction. Near-zero
support expected for `reading comprehension`, `algebra and functions`,
`hand tools`, and `power tools` (only the aptitude-prep documents
mention them; postings assume them) — keep them, the résumé/aptitude
-phase value stands alone. Raw counts for `nec`, `emt`, `awg`, `osha`,
`algebra` are untrustworthy (short/ambiguous tokens) — read per-alias
counts, not per-entry totals, for those entries.

## Overlap with existing tracks

**None — the first zero-overlap track.** No shared entries with any of
the thirteen tech tracks; the only collisions are lexical accidents
(`transformers`, `troubleshooting`, `algebra`-vs-`linear algebra`),
resolved above by ceding the bare tokens. Forward overlap is the real
story: this profile is the template for future skilled-trades tracks,
and its safety/tooling/blueprint entries (`skill.osha-10`,
`skill.hand-power-tools`, `skill.blueprint-reading`,
`skill.electrical-safety`'s `lockout tagout`,
`skill.reading-comprehension`) are the seed of a future trades
shared-entry cluster in `../02-shared-entries.md`.
