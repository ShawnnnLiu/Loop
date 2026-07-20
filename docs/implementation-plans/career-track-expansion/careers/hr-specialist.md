# HR Specialist / Recruiter — Track Profile

**Proposed enum value:** `hr_specialist` · **Wave 4** · Research grounded
2026-07-19.

## Track decision

One track covering both the HR generalist/specialist path and the
recruiter/talent-acquisition path. They share the same certification
ladder (aPHR → PHR / SHRM-CP), the same bodies of knowledge (recruiting
is one functional area inside both — Workforce Planning and Talent
Acquisition is 14% of the PHR outline,
https://www.hrci.org/docs/default-source/default-document-library/hrci_phr-exam-content-outline.pdf),
and the same behavioral/scenario interview loop; a recruiter's extra
vocabulary (sourcing, ATS, offer management) fits comfortably inside one
seed list. Per the granularity policy in `../01-expansion-mechanics.md`,
that is a merge; split only if enrichment later shows the two halves
barely co-occur.

Honesty note on the anchor: unlike PL-300 or AWS certs, **HR
certifications are optional for employment** — most postings list
aPHR/PHR/SHRM-CP as "preferred", not required, and SHRM-CP itself has no
degree or experience prerequisite. The cert ladder is the best *codified*
prep spine available, but it is a weaker forcing function than in
cert-defined tracks like cloud_engineer; plans should treat cert prep as
an optional backbone, with behavioral/scenario mocks and tool fluency as
the mandatory core.

**Resolver markers:** `"human resources"`, `"hr specialist"`,
`"hr generalist"`, `"hr coordinator"`, `"hr assistant"`,
`"hr business partner"`, `"hrbp"`, `"people operations"`, `"people ops"`,
`"recruiter"`, `"technical recruiter"`, `"talent acquisition"`,
`"sourcer"`, `"talent partner"`. Precedence hazards: `"hr analyst"` and
`"people analytics"` titles must be decided against data_analyst's bare
`"analytics"` marker — place `"hr analyst"` before it; `"people
analytics"` is genuinely DA-shaped work in an HR domain and is a
reconciliation judgment call. `"technical recruiter"` must resolve here,
never to `swe` (they recruit engineers, they aren't engineers). Bare
`"hr"` as a marker is boundary-matched so it works on titles like "HR
intern", but keep the multi-word markers ahead of it.

## Role snapshot

Recruits, screens, and hires candidates; administers onboarding,
benefits, compensation, employee relations, and compliance with
employment law (BLS OOH,
https://www.bls.gov/ooh/business-and-financial/human-resources-specialists.htm).
BLS: median $72,910 (May 2024), +6% growth 2024–34 (faster than
average), ~81,800 openings/yr — recruiters are counted inside this
occupation. Robert Half's 2026 demand list puts HR generalist, HR
specialist, recruiter, talent acquisition manager, compensation analyst,
and HRIS roles among the most-hired
(https://www.roberthalf.com/us/en/insights/research/data-reveals-which-hr-roles-are-in-highest-demand);
Indeed reports HR skills among the most sought-after across postings
(https://www.hrdive.com/news/hr-skills-among-most-sought-after/817418/).

## Prep-process profile

- **Interview loop:** recruiter screen → hiring-manager behavioral round
  (STAR-heavy: employee-relations scenarios, "walk me through a
  full-cycle req you owned") → scenario/panel round (mock intake meeting
  or sourcing exercise for recruiter roles; an ER investigation or
  policy case for generalist roles) → sometimes a practical exercise
  (write a job description, build a boolean sourcing string, run a mock
  phone screen) → values/leadership close. Metrics fluency is probed
  throughout (time-to-fill, offer-accept rate, turnover/retention) —
  the PHR outline itself names attrition, time-to-hire, and time-to-fill
  as expected data literacy. Question banks: Workable's recruiter
  interview bank (https://resources.workable.com/recruiter-interview-questions).
- **Exam pipeline (optional anchor, see track decision):**
  - **aPHR** — no experience/degree required, the true entry credential;
    90 questions in 1h45m; 2026 outline weights Compliance & Risk
    Management 25% and Employee Relations 24% heaviest
    (https://www.hrci.org/certifications/individual-certifications/aphr).
  - **PHR** — experience-gated (1–4 yrs depending on degree); published
    functional-area weights: Business Management 14%, Workforce Planning
    & Talent Acquisition 14%, Learning & Development 10%, Total Rewards
    15%, Employee Engagement 17%, Employee & Labor Relations 20%, HR
    Information Management 10%
    (https://www.hrci.org/docs/default-source/default-document-library/hrci_phr-exam-content-outline.pdf).
  - **SHRM-CP** — 134 questions, knowledge + situational-judgment items;
    scoped by the SHRM BASK (People / Organization / Workplace knowledge
    domains + behavioral competency clusters); no degree, HR title, or
    experience required to sit
    (https://www.shrm.org/credentials/certification/shrm-cp,
    https://www.shrm.org/content/dam/en/shrm/credentials/shrm-certification/shrm-bask.pdf).
- **Typical 12-week arc:** HR fundamentals + employment-law literacy
  (FLSA/FMLA/Title VII/EEO basics) → full-cycle recruiting mechanics +
  ATS/sourcing practice → comp & benefits, HRIS, and people-metrics
  literacy → behavioral/scenario mocks with readouts + cert
  sit-or-defer decision.

## Seed skill entries (draft)

Frequency grounding: employers most value HRIS/digital HR proficiency,
data analysis and HR reporting, employee relations, onboarding, and
communication (AIHR skills guide, https://www.aihr.com/blog/hr-skills/;
Robert Half career-path guide,
https://www.roberthalf.com/us/en/insights/landing-job/hr-career-paths-skills-job-search-strategies).
ATS reality check for tool aliases: Workday, Greenhouse, Lever, and
iCIMS dominate US enterprise postings
(https://leonstaff.com/blogs/which-ats-does-my-target-company-use/).

### Existing entries — add `hr_specialist` tag (~3)

`skill.excel` (defined in data-analyst.md — HR reporting lives in
spreadsheets), `skill.stakeholder-communication` (defined in
data-analyst.md; secondary tag — in nearly every HR posting),
`skill.compliance` (defined in cloud-engineer.md, CE/SA) — **CONTESTED
add-tag (2°)**: bare `compliance` and its aliases stay CE/SA-flavored
(SOC 2, FedRAMP); HR's compliance substance lives on the new
`skill.employment-law` below via `hr compliance`. Central reconciliation
decides whether the cross-domain tag is worth the noise. Nothing else in
the v1 taxonomy applies — HR is nearly disjoint from the engineering
vocabulary, and that's expected.

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.recruiting` | Full-Cycle Recruiting | `recruiting`, `recruitment`, `full-cycle recruiting`, `full cycle recruiting`, `talent acquisition`, `technical recruiting` | practice | hr_specialist | The recruiter half's core; `talent acquisition` is the posting-side spelling |
| `skill.sourcing` | Candidate Sourcing | `candidate sourcing`, `sourcing`, `boolean search`, `linkedin recruiter`, `passive candidates`, `talent sourcing` | practice | hr_specialist | Recruiter screens include live sourcing exercises; bare `sourcing` flagged below |
| `skill.ats` | Applicant Tracking Systems | `applicant tracking system`, `applicant tracking systems`, `ats`, `greenhouse`, `lever`, `icims`, `workday recruiting` | tool | hr_specialist | Top-4 US enterprise ATSes as aliases; `ats`/`greenhouse`/`lever` FTS-noisy, see below |
| `skill.hris` | HRIS Platforms | `hris`, `workday`, `sap successfactors`, `successfactors`, `bamboohr`, `adp`, `ukg`, `hcm` | tool | hr_specialist | Named a top employer demand (AIHR); bare `workday` lives here, `workday recruiting` on `skill.ats` |
| `skill.onboarding` | Onboarding & Offboarding | `onboarding`, `employee onboarding`, `new hire orientation`, `offboarding` | practice | hr_specialist | Core coordinator/generalist duty; PM may later want product "user onboarding" — see collision notes |
| `skill.employee-relations` | Employee Relations | `employee relations`, `workplace investigations`, `grievance handling`, `disciplinary actions`, `workplace conflict resolution` | practice | hr_specialist | Heaviest PHR domain (with labor relations, 20%); bare `conflict resolution` is CONTESTED (mobile owns it) |
| `skill.employment-law` | Employment Law & Compliance | `employment law`, `labor law`, `hr compliance`, `eeoc`, `eeo`, `flsa`, `fmla`, `title vii` | concept | hr_specialist | aPHR's largest domain (25%); the distinguishing multi-word `hr compliance` keeps bare `compliance` with CE/SA |
| `skill.compensation-benefits` | Compensation & Benefits | `compensation`, `benefits administration`, `total rewards`, `payroll`, `salary benchmarking`, `open enrollment` | practice | hr_specialist | PHR Total Rewards 15%; folding `payroll` in is a curation call (payroll-specialist roles exist) |
| `skill.behavioral-interviewing` | Structured & Behavioral Interviewing | `behavioral interviewing`, `structured interviewing`, `competency-based interviewing`, `phone screening`, `candidate screening`, `interview techniques` | practice | hr_specialist | Deliberately NOT bare `interviewing` (candidates interview too) and NOT `star method` (homed on PM's `skill.interview-frameworks`) |
| `skill.offer-management` | Offers & Pre-Employment Process | `offer management`, `offer negotiation`, `closing candidates`, `background checks`, `reference checks`, `salary negotiation` | practice | hr_specialist | Recruiter close-side; `salary negotiation` appears in every track's *prep* prose — per-track corpus tagging contains the noise |
| `skill.employee-engagement` | Employee Engagement & Retention | `employee engagement`, `engagement surveys`, `pulse surveys`, `retention strategies` | practice | hr_specialist | Its own PHR domain (17%) |
| `skill.performance-management` | Performance Management | `performance management`, `performance reviews`, `performance appraisal`, `360 feedback`, `performance improvement plan` | practice | hr_specialist | NEVER alias `pip` (python's installer); distinct from v1 `skill.performance-optimization` |
| `skill.learning-development` | Learning & Development | `learning and development`, `l&d`, `training and development`, `employee training`, `corporate training` | practice | hr_specialist | PHR L&D 10%; bare `training` deliberately not claimed (too generic) |
| `skill.workforce-planning` | Workforce & Org Planning | `workforce planning`, `headcount planning`, `succession planning`, `org design`, `organizational design` | concept | hr_specialist | PHR Workforce Planning 14%; SHRM Organization domain |
| `skill.people-analytics` | People Analytics & HR Metrics | `people analytics`, `hr analytics`, `hr metrics`, `workforce analytics`, `time-to-fill`, `turnover analysis` | concept | hr_specialist | Named hottest HR cluster (Robert Half); `kpis` stays on `skill.metric-definition` |
| `skill.employer-branding` | Employer Branding | `employer branding`, `employer brand`, `recruitment marketing`, `candidate experience` | practice | hr_specialist | PHR 1.5 names employer branding explicitly |
| `skill.dei` | DEI & Inclusive Hiring | `diversity and inclusion`, `diversity equity and inclusion`, `dei`, `deib`, `inclusive hiring` | concept | hr_specialist | SHRM Inclusive Mindset competency; postings staple |
| `skill.labor-relations` | Labor Relations | `labor relations`, `collective bargaining`, `union relations` | concept | hr_specialist | Half of the PHR's largest domain; niche in tech, heavy elsewhere |
| `skill.change-management` | Change Management | `change management`, `organizational change` | concept | management_consultant, hr_specialist | NEW·shared (ruled 2026-07-19): defined in management-consultant.md (identical mint) — listed here for the hr_specialist tag; SHRM Organization domain; PHR 1.3 names it |

**Optional / deferred** (protect the ≤100 budget; add only on enrichment
or user demand): payroll systems as a distinct entry (`gusto`, `rippling`,
`paychex`), `skill.exit-interviews` (fold into engagement for now),
immigration/visa sponsorship process, HR project management, job
description writing as its own entry, `google sheets` add-tag,
`skill.metric-definition` add-tag (2°), workplace safety/OSHA (aPHR
touches it; near-zero in tech-adjacent postings).

Running total: 19 new + 3 tagged ≈ **22 entries** — smallest track so
far, well under budget, mirroring that HR prep is breadth-of-domain
rather than tool-ladder deep. Kind skew is practice/concept-heavy with
zero language/framework entries; that is correct for this career, not a
gap.

## Alias-collision & FTS5 notes

- `hr` is a short/noisy FTS token — never an alias; trust `human
  resources` and the multi-word forms for enrichment interpretation.
  Same for `ats` (trust `applicant tracking system`), `dei` (trust
  `diversity and inclusion`), `l&d`, `eeo`/`eeoc`, `adp`, `hcm`.
- `greenhouse` and `lever` collide with ordinary English in prose
  (greenhouse gases, lever/leverage); fine for résumé resolution,
  advisory-only for FTS counts — per-alias counts will disambiguate.
- **CONTESTED — reconciliation must rule:**
  - `compliance` (bare + framework aliases) — homed on
    `skill.compliance` (cloud-engineer.md, CE/SA). HR proposes add-tag
    (2°) only; HR mints `hr compliance` on `skill.employment-law`
    instead of claiming the bare token.
  - `conflict resolution` — homed on `skill.offline-first`
    (mobile-engineer.md) meaning data-sync conflicts. HR's employee
    relations meaning is arguably the dominant English one; this profile
    claims only `workplace conflict resolution` and leaves the bare
    form's re-homing to reconciliation.
  - `star method` — homed on `skill.interview-frameworks`
    (product-manager.md). HR behavioral-interview prep uses it too; not
    claimed here, but reconciliation may prefer re-homing it to a
    track-neutral interview-prep entry.
  - `onboarding` — claimed here for employee onboarding; if a future PM
    increment wants product/user onboarding, the multi-word split is
    `employee onboarding` (HR) vs `user onboarding` (PM), bare form
    stays HR.
- Deliberately NOT claimed: bare `interviewing` (every candidate in
  every track "interviews" — hopeless for both resolution and FTS), bare
  `training` (ML training, security-awareness training, strength
  training), bare `communication` and `recruiter` (role title, not
  skill), `job postings`/`job descriptions` (the corpus IS job postings
  — catastrophic FTS inflation), `pip` (python), bare `star`
  (deliberately homeless per `../02-shared-entries.md`).
- `performance management` vs v1 `skill.performance-optimization`
  (`performance optimization`, `performance tuning`): no alias overlap,
  but FTS prefix noise on "performance" prose — trust the full
  multi-word counts.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/business-and-financial/human-resources-specialists.htm | role_taxonomy | Official occupational profile; stable; **serves 403 to plain fetchers** — anti-bot, may need manual snapshot |
| https://www.onetonline.org/link/summary/13-1071.00 | role_taxonomy | O*NET HR Specialists — richest official task/skill inventory; very stable, public |
| https://www.hrci.org/docs/default-source/default-document-library/hrci_phr-exam-content-outline.pdf | role_taxonomy | Official PHR outline PDF with domain weights; fetch verified 2026-07-19 |
| https://www.hrci.org/certifications/individual-certifications/aphr | role_taxonomy | Official aPHR page (entry credential, no-experience gate) |
| https://www.shrm.org/credentials/certification/shrm-cp | role_taxonomy | Official SHRM-CP page; marketing-page churn risk |
| https://www.shrm.org/content/dam/en/shrm/credentials/shrm-certification/shrm-bask.pdf | role_taxonomy | SHRM BASK PDF — canonical knowledge-domain taxonomy; large PDF, revised on multi-year cycle (2026 edition current) |
| https://www.aihr.com/blog/hr-skills/ | role_taxonomy | 18-skill practitioner taxonomy; refreshed yearly |
| https://www.aihr.com/blog/entry-level-hr-positions/ | role_taxonomy | Entry-path role guide; refreshed yearly |
| https://www.roberthalf.com/us/en/insights/research/data-reveals-which-hr-roles-are-in-highest-demand | role_taxonomy | Demand-by-role data; volatile yearly, treat figures as point-in-time |
| https://resources.workable.com/recruiter-interview-questions | interview_report | Interviewer-side recruiter question bank; stable for years |
| https://www.pin.com/blog/recruitment-process-guide/ | role_taxonomy | Full-cycle recruiting stage taxonomy (the recruiter's own craft) |
| https://leonstaff.com/blogs/which-ats-does-my-target-company-use/ | role_taxonomy | ATS market-share landscape; small-site link-rot risk |
| https://www.hrdive.com/news/hr-skills-among-most-sought-after/817418/ | interview_report | Indeed posting-demand reporting; news URL, volatile |
| (job boards: linkedin/indeed "hr specialist"/"recruiter" searches) | official_job_posting | Volatile + login-gated; sample per run |

## Enrichment expectations

Expect `talent acquisition`, `recruiting`, `onboarding`, `employee
relations`, `compensation`, `benefits administration`, `hris`,
`employment law` to dominate counts. Zero-support flags likely for
`boolean search`, `bamboohr`, `pulse surveys`, `workplace
investigations` (prose phrasing varies) — keep them; résumé-resolution
value stands alone. Ignore raw counts on `hr`, `ats`, `dei`,
`greenhouse`, `lever` per the notes above; per-alias counts are the
trustworthy signal for this track more than most.

## Overlap with existing tracks

Nearly disjoint from all thirteen existing tracks — the widest skill gap
of any career profiled, which is the point of adding it. Real touchpoints:
`skill.excel` and (2°) `skill.stakeholder-communication` shared with the
DA/PM cluster; `skill.people-analytics` sits adjacent to data_analyst
(an "HR analyst" résumé is the boundary case — see resolver markers);
`skill.compliance` cross-tags CE/SA only if the CONTESTED ruling allows.
A technical recruiter's knowledge *about* swe interview loops is domain
context, not shared skills — no swe entries are tagged. One-track
consequence restated: generalist and recruiter surfaces share this seed
list by design; enrichment data can justify a future split.
