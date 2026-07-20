# K-12 Teacher (Licensure via Praxis) — Track Profile

**Proposed enum value:** `teacher_k12` · **Wave 5** · Research grounded
2026-07-19.

## Track decision

Own track, **one track for all of K-12** — grade bands (elementary /
middle / high) and subject specializations (math teacher, english
teacher, science teacher) stay inside it, the same way frontend/backend
stay inside `swe`. Rationale: the prep process is shared across
specializations — same gate structure (degree → prep program → basic
skills test → subject test → pedagogy test/performance assessment →
background check → state application), same anchor exam family (Praxis,
https://praxis.ets.org/), same pedagogy core. Only the *subject
assessment* differs, and that is a per-user test-selection decision, not
a track boundary. **Open specialization question for curation:** whether
subject-content prep (e.g. "Praxis Biology 5236") warrants per-subject
entries later; this profile models it with one generic
`skill.praxis-subject-assessment` entry plus the elementary
multiple-subjects test, and defers per-subject explosion. Splitting
per-subject tracks would be the "too many tracks" mistake the mechanics
doc warns about: each would need its own corpus and markers for a
near-identical prep arc.

This is an exam/licensure (wave-5) career: read
`../03-wave-3-exam-careers.md` first. All five of its strain points
apply — credential gates, blueprint/version mapping (here:
**state-by-state variance**), hard exam dates, `concept`-heavy kind
skew, and an official-blueprint-anchored corpus.

**Resolver markers:** `"teacher"`, `"teaching"`, `"educator"`,
`"school teacher"`, `"substitute teacher"`, `"paraprofessional"`,
`"teacher certification"`, `"teaching license"`. Bare `"teacher"` with
word-boundary matching catches the whole family ("high school math
teacher", "elementary teacher", "special education teacher"), so
per-subject markers are unnecessary. Precedence hazards: none of the 13
existing tracks (swe, mle, ai_engineer, quant_dev, data_scientist,
data_analyst, data_engineer, devops_sre, cloud_engineer,
security_analyst, product_manager, ux_designer, mobile_engineer) marker
on any of these tokens, but place `teacher_k12` **before** `swe` so
"computer science teacher" resolves here, not to anything
engineering-adjacent. Known ambiguity to accept: "teaching assistant"
(K-12 paraprofessional vs university TA) and "educator" (rarely
"developer educator") — both resolve here; a university-TA-headed-to-swe
user types their target role, not their current one, so the miss rate is
low. Postsecondary professor is out of scope for this track.

## Role snapshot

Plans and delivers instruction, manages a classroom, assesses student
learning, and communicates with families; licensure is state-issued and
exam-gated. Large, stable-by-replacement demand: BLS projects ~103,800
openings/yr for kindergarten & elementary teachers (medians $61,430
kindergarten / $62,340 elementary,
https://www.bls.gov/ooh/education-training-and-library/kindergarten-and-elementary-school-teachers.htm),
~40,500/yr for middle school (median $62,970,
https://www.bls.gov/ooh/education-training-and-library/middle-school-teachers.htm),
and ~66,200/yr for high school (median $64,580,
https://www.bls.gov/ooh/education-training-and-library/high-school-teachers.htm)
— ~210k openings/yr combined, essentially all replacement (employment
itself projected −2% 2024–34). The Praxis family is the dominant
licensure exam system — ETS's Core tests are used for entry/initial
certification in 30+ states and territories, and Praxis is used to some
extent in the large majority of states
(https://praxis.ets.org/state-requirements.html) — but several big
states run their own systems (CA: CBEST/CSET; IL: ILTS; MI: MTTC; FL:
FTCE), which is exactly the state-variance gate below.

## Prep-process profile

### Credential-prerequisite gates (mirror `../03-wave-3-exam-careers.md`)

These are **not skills** and must not become taxonomy entries. The
Planner must refuse to schedule exam prep around an unmet gate rather
than treat it as a weak spot:

1. **Bachelor's degree** (any subject for elementary; usually
   subject-relevant for secondary).
2. **State-approved educator preparation program** — traditional
   (undergrad/post-bac) or alternative route; alternative routes still
   require the same state tests, often *before* program admission
   (https://www.teachercertificationdegrees.com/alternative/).
3. **State pin — the blueprint-version analog.** Which tests exist at
   all (Praxis vs CBEST/CSET/ILTS/MTTC/FTCE), which Praxis codes, and
   what qualifying scores apply are 100% state-determined
   (https://praxis.ets.org/state-requirements.html). No test-prep task
   is schedulable until the target state is pinned, same as pinning a
   CPA/NCLEX blueprint revision. A state move mid-prep is a re-plan
   trigger.
4. **Student teaching / clinical hours** — program-scheduled, not
   plannable as self-study; a hard calendar constraint the scheduler
   consumes, not produces.
5. **Performance assessment where required** — edTPA or a state TPA;
   state policy churns (NY dropped it 2022, IL suspended through 2025,
   "edTPA Essentials" redesign launches Aug 2026 —
   https://edtpa.org/resource_item/StatePolicyOverview). Another reason
   the state pin is load-bearing.
6. **Fingerprint/background check + state application** — administrative
   gates with external latency; scheduling constants, not study tasks.

### Exam pipeline

- **Praxis Core Academic Skills for Educators** (Reading 5713 / Writing
  5723 / Math 5733, combined 5752) — the program-admission basic-skills
  gate (https://praxis.ets.org/test/5752.html). Math spans numbers &
  quantity, data interpretation, statistics & probability, algebra,
  geometry; Writing includes two essays.
- **Praxis Subject Assessment** for the target license area — e.g.
  Elementary Education: Multiple Subjects 5001 with four subtests
  (Reading/LA 5002, Math 5003, Social Studies 5004, Science 5005;
  https://praxis.ets.org/test/elementary-education-multiple-subjects-subtests-5001.html),
  or a single-subject content test for secondary.
- **Principles of Learning and Teaching (PLT)** where the state requires
  a pedagogy test — published category weights, e.g. PLT 7–12 (5624):
  Students as Learners 22.5%, Instructional Process 22.5%, Assessment
  15%, Professional Development/Leadership/Community 15%, case-history
  constructed responses 25%
  (https://praxis.ets.org/on/demandware.static/-/Library-Sites-ets-praxisLibrary/default/pdfs/5624.pdf).
  Published weights make proportional coverage validation exact — the
  wave-5 sweet spot.
- **edTPA / state TPA** where required (portfolio: planning,
  instruction videos, assessment commentary), during student teaching.
- **Anchor resources:** official ETS test pages + free study companions
  and prep resources (https://www.ets.org/praxis/prepare/study/);
  teach.org state-by-state pathway guide
  (https://www.teach.org/becoming-teacher); InTASC Model Core Teaching
  Standards (CCSSO,
  https://ccsso.org/resource-library/intasc-model-core-teaching-standards)
  and the Danielson Framework for Teaching
  (https://danielsongroup.org/the-framework-for-teaching/) as the
  pedagogy vocabulary anchors. Never ingest commercial prep banks
  (Kaplan/240Tutoring/Mometrix-class) — free official material only.
- **Typical arc:** common guidance is 4–8 weeks per test — ~6 weeks for
  Core, 8–10 for the four-subtest 5001, 3–8 for a subject test
  depending on distance from the degree
  (https://www.240tutoring.com/praxis-prep/how-to-study-for-the-praxis/
  — cite-only, not corpus). A realistic serial pipeline: state pin +
  diagnostics → Core (6 wks) → subject assessment (4–8 wks) → PLT +
  pedagogy core (4 wks) → edTPA during student teaching → demo-lesson +
  district hiring loop. Fixed test dates and score-report latency are
  hard external deadlines (wave-5 strain #3).
- **Hiring loop** (post-license): district application → screening →
  panel interview → **demo lesson** (the teaching analog of the coding
  round) → reference/background checks.

## Seed skill entries (draft)

Kind skew is as `../03-wave-3-exam-careers.md` predicts: heavily
`concept`/`practice`, one `tool` entry, zero `language`/`framework`. Do
not add validation that assumes kind balance.

### Existing entries — add `teacher_k12` tag (~1)

Nothing in the 166-entry v1 taxonomy fits this career — it is tech-only
and K-12 teaching is disjoint from it (do **not** tag `skill.statistics`
etc. for Praxis Core math; that entry means ML-grade statistics). One
secondary tag on a NEW·shared entry from wave 1:
`skill.stakeholder-communication` (defined in `data-analyst.md`; owns
`stakeholder management`, `presentation skills`) — teacher_k12(2°),
defensible for admin/colleague communication; curation decides.
Family-facing communication gets its own entry below because postings
say "parent communication", not "stakeholder management".

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.praxis-core-reading` | Praxis Core Reading | `praxis core reading`, `praxis reading` | concept | teacher_k12 | Test 5713; passage comprehension + charts |
| `skill.praxis-core-writing` | Praxis Core Writing | `praxis core writing`, `praxis writing` | concept | teacher_k12 | Test 5723; grammar/usage + two essays |
| `skill.praxis-core-math` | Praxis Core Mathematics | `praxis core math`, `praxis core mathematics`, `praxis math` | concept | teacher_k12 | Test 5733; numeracy, algebra, geometry, data/stats |
| `skill.praxis-subject-assessment` | Praxis Subject Assessment | `praxis subject assessment`, `praxis subject assessments`, `praxis ii`, `praxis 2`, `praxis content knowledge` | concept | teacher_k12 | Generic license-area content test; per-subject explosion deferred |
| `skill.praxis-elementary-education` | Praxis Elementary Ed: Multiple Subjects | `elementary education multiple subjects`, `praxis 5001` | concept | teacher_k12 | Four subtests (5002–5005); the elementary anchor |
| `skill.plt-exam` | Principles of Learning and Teaching | `principles of learning and teaching`, `praxis plt`, `plt` | concept | teacher_k12 | Pedagogy test w/ published weights; `plt` short token — trust long alias |
| `skill.edtpa` | edTPA Performance Assessment | `edtpa` | concept | teacher_k12 | Distinctive token; `tpa` and bare `portfolio` deliberately NOT claimed |
| `skill.pedagogy` | Pedagogy & Learning Theory | `pedagogy`, `learning theory`, `learning theories`, `blooms taxonomy`, `bloom's taxonomy` | concept | teacher_k12 | Both apostrophe spellings pending normalizer check |
| `skill.lesson-planning` | Lesson Planning | `lesson planning`, `lesson plans`, `unit planning`, `backward design` | practice | teacher_k12 | Core deliverable of every teaching job + edTPA Task 1 |
| `skill.classroom-management` | Classroom Management | `classroom management`, `behavior management`, `classroom procedures`, `pbis` | practice | teacher_k12 | #1 topic in teacher interviews and new-teacher failure modes |
| `skill.instructional-delivery` | Instructional Delivery | `direct instruction`, `instructional strategies`, `checking for understanding`, `questioning techniques` | practice | teacher_k12 | `public speaking` wanted but CONTESTED — see notes |
| `skill.differentiated-instruction` | Differentiated Instruction | `differentiated instruction`, `differentiation`, `scaffolding`, `universal design for learning`, `udl` | practice | teacher_k12 | `differentiation` collides with calculus prose — FTS noise |
| `skill.assessment-design` | Assessment & Grading | `formative assessment`, `summative assessment`, `assessment design`, `rubrics`, `grading`, `progress monitoring` | practice | teacher_k12 | Bare `assessment` deliberately NOT claimed (homeless candidate) |
| `skill.data-driven-instruction` | Data-Driven Instruction | `data-driven instruction`, `data driven instruction` | practice | teacher_k12 | Interpreting student data; distinct from analyst data skills |
| `skill.student-engagement` | Student Engagement & Motivation | `student engagement`, `student motivation` | concept | teacher_k12 | PLT "Students as Learners" territory |
| `skill.child-development` | Child & Adolescent Development | `child development`, `adolescent development`, `developmental psychology` | concept | teacher_k12 | PLT category anchor |
| `skill.special-education` | Special Education Foundations | `special education`, `sped`, `iep`, `individualized education program`, `504 plan` | concept | teacher_k12 | General-ed literacy level; SPED-license track would be separate later |
| `skill.ell-instruction` | English Learner Instruction | `english language learners`, `ell`, `esl`, `esol`, `sheltered instruction` | practice | teacher_k12 | `ell`/`esl` short tokens — trust long aliases |
| `skill.literacy-instruction` | Literacy Instruction | `literacy instruction`, `science of reading`, `phonics` | practice | teacher_k12 | Elementary-critical; science-of-reading laws spreading state-by-state. `reading comprehension` ruled 2026-07-19 to electrician's aptitude-test entry (`skill.reading-comprehension`) — the distinctive teaching forms stay here |
| `skill.curriculum-standards` | Curriculum & Standards Alignment | `curriculum design`, `curriculum development`, `common core`, `standards alignment`, `state standards` | concept | teacher_k12 | Standards are the teaching analog of a spec |
| `skill.classroom-technology` | Classroom Technology | `google classroom`, `edtech`, `education technology`, `learning management system`, `lms` | tool | teacher_k12 | The track's only `tool`; `lms` flagged in notes |
| `skill.family-communication` | Family & Community Engagement | `parent communication`, `parent-teacher conferences`, `family engagement` | practice | teacher_k12 | PLT "Community" category; interview staple |
| `skill.social-emotional-learning` | Social-Emotional Learning | `social-emotional learning`, `social emotional learning`, `sel` | concept | teacher_k12 | `sel` short token — trust long aliases |
| `skill.culturally-responsive-teaching` | Culturally Responsive Teaching | `culturally responsive teaching` | concept | teacher_k12 | Common posting/interview phrase; single distinctive alias |
| `skill.demo-lesson` | Demo Lesson & Hiring Loop | `demo lesson`, `teaching demonstration`, `teacher interview` | practice | teacher_k12 | The hiring loop's technical round |

**Optional / deferred** (protect the budget; add only on enrichment or
user demand): per-subject Praxis content entries (math 5165, english
5039, biology 5236, social studies 5081...), classroom assessment
platforms as tools, gifted education, co-teaching models, restorative
practices, National Board Certification (in-service, not entry
licensure), `skill.timed-practice-exams` as a cross-exam-career shared
entry (see notes — reconciliation owns it).

Tally: 25 new + 1 existing secondary ≈ 26 — far under the ~100 prompt
budget, leaving room for per-subject content entries later.

## Alias-collision & FTS5 notes

- **`praxis` is the track's distinctive high-value FTS token** — near
  zero false positives in general prose; every exam entry carries a
  `praxis`-prefixed long alias, so per-entry enrichment counts are
  trustworthy.
- **Bare `assessment` is deliberately NOT claimed** (homeless
  candidate): teacher assessment design vs security assessment vs UX
  usability assessment vs exam-career "practice assessment" — 
  unwinnable. `skill.assessment-design` stands on `formative
  assessment`/`summative assessment`/`rubrics`. Reconciliation should
  add it to 02's deliberately-homeless list.
- **CONTESTED — `public speaking`:** wanted for
  `skill.instructional-delivery`; unclaimed by v1 and all nine wave-1/2
  profiles, but any people-facing future career (law/bar, sales,
  postsecondary) could want it. Not listed as an alias above;
  reconciliation makes the ruling.
- **CONTESTED — `test-taking strategies`, `practice tests`, `timed
  practice`:** every wave-5 exam career (CPA, CFA, bar, NCLEX, PMP)
  drills these; they belong on ONE shared entry
  (`skill.timed-practice-exams`-shaped) created once by whichever
  exam-career increment lands first, per the 02 registry pattern. Not
  claimed here.
- **NOT claimed, likely wanted by nurse/NCLEX:** `clinical practice`,
  `practicum`, `clinical judgment`. Student teaching is modeled as a
  credential gate, not a skill, so this track needs none of them.
- **Respected homeless tokens** (02): `portfolio` (edTPA is one — entry
  keeps only `edtpa`), `documentation`, `star`. `tpa` not claimed
  (third-party administrator noise).
- **Short/noisy tokens flagged:** `plt`, `sel`, `ell`, `esl`, `esol`,
  `sped`, `udl`, `iep`, `pbis`, `lms` — acceptable for résumé
  resolution, optimistic in FTS counts; trust the paired long aliases.
  `iep` is claimed here but a future school-counselor/SLP career would
  co-want it — flag for reconciliation memory. `lms` / `learning
  management system` would be co-wanted by a future
  instructional-designer career.
- **FTS noise:** `differentiation` (calculus prose), `grading` (also
  "grading rubric" in generic contexts), `reading comprehension`
  (appears in Praxis Core Reading prose too — cross-entry double
  counting within this track is harmless but expect it).
- No collisions against the v1 alias table (checked: the taxonomy is
  tech-only; no `teach*`, `lesson*`, `classroom*`, `pedagog*`,
  `curricul*`, `praxis*` aliases exist) or against 02's NEW·shared
  rows/rulings.

## Candidate corpus sources (manifest seeds)

Wave-5 manifest rule applies: official blueprints + free explainers
only; never ingest commercial prep material (Kaplan/240Tutoring/
Mometrix/Study.com-class).

| URL | expected type | note |
|---|---|---|
| https://praxis.ets.org/ | role_taxonomy | Official program home; very stable |
| https://praxis.ets.org/test/5752.html | role_taxonomy | Core combined (5713/5723/5733) official scope; stable |
| https://praxis.ets.org/on/demandware.static/-/Library-Sites-ets-praxisLibrary/default/pdfs/5001.pdf | role_taxonomy | Official 5001 study companion PDF w/ domain breakdown; versioned by ETS |
| https://praxis.ets.org/on/demandware.static/-/Library-Sites-ets-praxisLibrary/default/pdfs/5624.pdf | role_taxonomy | Official PLT 7–12 companion w/ category weights; versioned |
| https://praxis.ets.org/state-requirements.html | role_taxonomy | THE state-variance anchor; content churns as states change policy — re-fetch each snapshot |
| https://www.ets.org/praxis/prepare/study/ | role_taxonomy | Official free prep resources; stable |
| https://www.teach.org/becoming-teacher | role_taxonomy | DOE-partnered state-by-state pathway guide; stable |
| https://ccsso.org/resource-library/intasc-model-core-teaching-standards | role_taxonomy | InTASC standards — the canonical pedagogy vocabulary; very stable PDF |
| https://danielsongroup.org/the-framework-for-teaching/ | role_taxonomy | Danielson observation framework; the evaluation-rubric vocabulary |
| https://edtpa.org/resource_item/StatePolicyOverview | role_taxonomy | edTPA state policy overview; revised ~annually — volatility noted |
| https://www.bls.gov/ooh/education-training-and-library/high-school-teachers.htm | role_taxonomy | BLS role guide (how-to-become section); public domain, annual refresh |
| https://www.bls.gov/ooh/education-training-and-library/kindergarten-and-elementary-school-teachers.htm | role_taxonomy | Same, elementary band; public domain |
| https://www.teachercertificationdegrees.com/alternative/ | role_taxonomy | Free alt-route explainer; refreshed yearly |
| (district job boards: K12JobSpot, state DOE boards, indeed "teacher" searches) | official_job_posting | Volatile + 45-day decay; sample per run |
| (r/Praxis, teacher-forum exam-experience threads) | interview_report | Closest analog to interview reports for an exam career; volatile |

## Enrichment expectations

`praxis`, `classroom management`, `lesson planning`, `special
education`, `iep`, `differentiated instruction`, `common core` should
dominate counts — blueprint PDFs and postings both use these verbatim.
Zero-support flags likely for `demo lesson` (hiring-loop prose is
thin in official corpora), `praxis 2`/`praxis ii` (official pages say
"Subject Assessments" now), and `culturally responsive teaching` in the
ETS PDFs (appears in InTASC/postings instead) — keep all; résumé/
plan-resolution value stands alone. Expect the wave-5 inversion: counts
concentrated in a few official PDFs rather than spread across many
volatile postings, so `supporting_doc_ids` breadth will look narrow
compared to tech tracks — that is corpus shape, not weak evidence.

## Overlap with existing tracks

Effectively disjoint from all thirteen tech tracks — zero shared
languages/frameworks/tools except arguably classroom edtech. The only
touchpoint is soft-skill: `skill.stakeholder-communication` (2°). Do
NOT let Praxis Core math/reading/writing map onto
`skill.statistics`/tech entries — same words, different meaning and
level; the track needs its own exam-scoped entries. Within wave 5,
teacher_k12 shares the *shape* of CPA/CFA/NCLEX/bar (gates, blueprints,
hard test dates) and should share the contested timed-practice shared
entry, but zero domain vocabulary.
