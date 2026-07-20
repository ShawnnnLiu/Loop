# Career Track Expansion — Research-Grounded Planning Docs

Written 2026-07-06; extended 2026-07-19 with a second research pass
adding fifteen wave-4/5 profiles. Status: **planning docs only — nothing
here is implemented.** These docs exist so that when a new career track is added,
the three requirements (enum membership, curated taxonomy entries,
track-tagged corpus documents) can be satisfied from a researched draft
instead of from scratch — and so the RI-F enrichment run over the
grounding-RAG corpus has per-track alias lists and corpus manifests ready
to use.

Every skill list, prep-process profile, and corpus source table below was
grounded in a web-research pass on the date above (job-posting frequency
analyses, official certification syllabi, role guides, interview guides —
cited inline in each profile). Posting counts and salary figures are
point-in-time; the structural claims (loop stages, cert domains, skill
clusters) decay much slower.

## How these docs plug into existing plans

- **`resume-intake-onboarding/06-skill-taxonomy.md`** defines the
  controlled vocabulary, the shared `CareerTrack` enum, and RI-F
  (corpus-evidence enrichment — built as `tools/enrich_taxonomy.py`).
  These docs supply the *content* a new track needs: seed `SkillEntry`
  drafts with FTS5-conscious aliases.
- **`loop-grounding-rag/01-corpus-and-contracts.md`** reserves G-I for
  "remaining tracks after the pipeline is proven." A career landed via
  this folder's checklist **is** a G-I increment: each profile's corpus
  source table seeds the ingestion manifest (URL, expected `source_type`,
  track tags, license note).
- Curation stays human: these drafts are LLM-researched but land only
  through review, per axiom 08's controlled-vocabularies wall. The review
  is the gate.

## Doc map

| Doc | What it holds |
|---|---|
| `01-expansion-mechanics.md` | The repeatable checklist: enum amendment (spec-first) → taxonomy version bump (≤ ~100 entries/track prompt budget) → resolver markers → corpus manifest → enrichment run → evals. Plus alias-design-for-FTS5 rules and the track granularity policy. **Read first.** |
| `02-shared-entries.md` | Cross-career registry of shared new entries and single-home alias rulings — the doc that protects global alias uniqueness when careers land in separate increments. **Check before implementing any career.** |
| `03-wave-3-exam-careers.md` | Scan of CPA/CFA/PMP/NCLEX/bar: where blueprints fit the system beautifully and the two genuinely new contract needs (credential-prerequisite nodes, blueprint-version mapping). |
| `careers/*.md` | One profile per career: track decision + resolver markers, prep-process shape, seed skill entries (NEW vs EXISTING-add-tag), alias-collision notes, corpus manifest seeds, enrichment expectations. |

## Wave roadmap

Ordering logic: popularity × prep-process codification × implementation
cost (shared-entry reuse). Each career is a self-contained increment —
one review, one taxonomy version, one manifest addition.

**Wave 1 — popular, codified, adjacent** (any order, though
`devops_sre` before `cloud_engineer` and `data_analyst` before the other
data careers minimizes shared-entry churn):

1. `data_analyst` — most codified prep of any career researched; ~35
   entries, mostly new but cheap ones.
2. `data_scientist` — BLS's 4th fastest-growing occupation; rides the
   `mle` vocabulary (~30 entries are just track tags).
3. `data_engineer` — 84k+ postings; rides `swe`+`mle` infrastructure
   vocabulary.
4. `devops_sre` — one track for DevOps/SRE/platform (evidence in
   profile); lands the ops shared-entry cluster the later infra tracks
   reuse.
5. `security_analyst` — exceptional demand (29% BLS growth, 74 workers
   per 100 openings) and the best-licensed corpus of all (NIST/CISA
   public domain); most expensive vocabulary (~35 new entries).
6. `product_manager` — most codified non-engineering career; first
   non-engineering stressor for the taxonomy kinds.

**Wave 2 — codified but overlapping or product-gapped:**

7. `cloud_engineer` — own track but lands after `devops_sre` (~60%
   shared graph arrives as tags).
8. `mobile_engineer` — own track that heavily reuses the `swe` base
   (the marginal granularity case; reasoning in profile).
9. `ux_designer` — needs artifact-milestone plan framing (portfolio
   work, not question drilling) before the track is honest; flagged as a
   plan-generation concern in the profile.

**Wave 3 — exam/licensure careers** (see `03-…`): gated on two wave-1
careers proven end-to-end plus a credential-prerequisite contract spec.
PMP first when it opens.

**Wave 4 — cert/interview-codified, beyond tech** (researched
2026-07-19; popularity ranked by BLS openings/growth × active-prepper
volume × prep codification; rides existing machinery like waves 1–2):

10. `it_support` — ~50k openings/yr; CompTIA A+ V15 + Google IT cert;
    the standard IT on-ramp, several rungs below devops/cloud.
11. `digital_marketer` — 127k+ open roles (Google's revised figure);
    Google/HubSpot cert stack; near-zero taxonomy overlap (~28 new).
12. `management_consultant` — ~98k openings/yr; the case-interview canon
    is the most codified non-exam loop anywhere; deadline-anchored
    recruiting calendar is a scheduling-relevant constraint.
13. `business_analyst` — same BLS SOC; BABOK/ECBA→CBAP ladder;
    **re-homes the `business analyst` resolver marker from
    `data_analyst`** (coordinated marker edit, done in both profiles).
14. `network_engineer` — 331k jobs; CCNA→CCNP canon; lands the network
    vocabulary it_support tags instead of minting.
15. `hr_specialist` — ~82k openings/yr; aPHR/PHR/SHRM-CP (optional-cert
    caveat recorded honestly); one track covers generalist + recruiter.
16. `financial_analyst` — ~30k openings/yr; modeling-test/BIWS canon +
    FMVA; explicit boundary drawn against wave-3 CFA (clean-room kept).
17. `salesforce_admin` — smaller posting base (vendor hype discounted in
    the profile) but a large self-study population on a free codified
    curriculum (Trailhead; 2025-12-15 exam refresh weights recorded).

**Wave 5 — licensure/exam-gated** (wave-3 pattern: credential-prereq
gates, blueprint versioning, concept-heavy kind skew; same gating rule
as wave 3 — do not start before the credential-prerequisite contract
spec exists):

18. `teacher_k12` — 200k+ openings/yr across grade bands; Praxis
    Core/Subject/PLT + edTPA; state variance = blueprint-version analog.
19. `real_estate_agent` — ~46k openings/yr, highest-churn licensure
    career; per-state course-hours + PSI/Pearson VUE exam; "state" must
    become a plan-level input.
20. `financial_advisor` — +10% growth; SIE→Series 7→65/66→CFP ladder;
    Series 7's firm-sponsorship gate is the canonical "Planner must
    refuse to schedule around it" case.
21. `insurance_agent` — ~47k openings/yr; per-line state exams with
    published weighted outlines; serial multi-line gate chains.
22. `actuary` — tiny headcount (~2.4k openings/yr) but near-perfect
    product fit: SOA/CAS ladder, 300+ scheduled hrs/exam for years.
23. `medical_coder` — 250k+ AAPC members; CPC/CCS; code-set versioning
    (ICD Oct 1 / CPT Jan 1) is a literal blueprint-version problem.
24. `electrician` — ~81k openings/yr; trades proxy/template; only the
    bookends (apprenticeship aptitude test, NEC journeyman exam) are
    schedulable study — the profile is honest that the multi-year middle
    is employment, not prep.

Wave-4/5 cross-career alias rulings (sales cluster, exam-practice
entry, powerpoint/m&a/change-management homes, the `hipaa` re-home) are
recorded in `02-shared-entries.md` § "Wave 4–5 additions" — read that
section before implementing ANY of these fifteen.

**Next-up (researched and cut just below the top 15, in order):**
physician_assistant (PANCE), pharmacist (NAPLEX), physical_therapist
(NPTE), emt_paramedic (NREMT), supply_chain_analyst (APICS CSCP/CPIM),
scrum_master (high fold-risk into the PMP track — revisit only after
PMP lands), paralegal (flat outlook, AI headwinds).

**Explicit non-tracks:** frontend/backend/full-stack stay inside `swe`
(same loop shape; the resolver already homes them there). QA engineer,
solutions architect, TPM, and analytics engineer were considered and
folded or deferred (analytics engineer → `data_engineer` markers; TPM
deliberately unresolved → union fallback). The 2026-07-19 pass added:
penetration tester → `security_analyst` specialization (OSCP noted, same
pattern as the QA ruling); game developer and embedded/firmware →
portfolio + standard `swe` loops; customer success manager and tech
sales → prep essentially uncodified (no artifact to schedule); technical
writer and DBA → too small / DBA folds into `data_engineer` per the
analytics-engineer precedent.

## What "helpful for RAG enrichment later" concretely means here

Each career profile was written against the enrichment tool's actual
mechanics (RI-F: count alias occurrences per track via FTS5 over a pinned
snapshot; flag zero-support entries for human review):

- **Aliases are the search terms.** Every seed entry carries the
  spellings job postings and syllabi actually use (`power bi`/`powerbi`,
  `k8s`, `spl`), lowercase-normalized to the contract's rules.
- **Noisy-token warnings are pre-recorded.** Profiles flag which aliases
  will produce garbage counts (`swift`, `go`, `r`, `ids`, `bi`, `rice`)
  and which long-form aliases to trust instead — so a future RI-F report
  reader doesn't rediscover this per track. A per-alias (not just
  per-entry) count breakdown in the report is recommended in
  `01-expansion-mechanics.md`.
- **Corpus tables are manifest-shaped.** URL + expected `source_type` +
  license/volatility note per row, 10–15 stable anchors per track,
  with the classifier and axiom-08 expiry rules in mind (cert syllabi and
  NIST/BLS material anchor; job postings are sampled, never durable).
- **Enrichment expectations per track.** Each profile predicts its
  high-count aliases and its acceptable zero-support entries, turning the
  RI-F report review from an open-ended eyeball into a
  diff-against-expectations.

## Standing caveats

- Entry counts and status columns (NEW vs EXISTING) were drafted against
  `skill_taxonomy_v1.json` (166 entries) — re-verify against the current
  taxonomy version at implementation time.
- Resolver-marker precedence interacts across careers; re-derive the full
  `_TRACK_MARKERS` order whenever a track is added, with tests.
- All sizes/thresholds here are heuristic priors until calibrated —
  the same status as every other threshold in the repo.
- Live corpus fetches remain ask-first, operator-run, per house rules.
