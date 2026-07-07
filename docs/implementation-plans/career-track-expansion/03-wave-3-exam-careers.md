# 03 · Wave 3 — Exam/Licensure-Driven Careers (Scan + System Fit)

Researched 2026-07-06 at scan depth: the five careers whose prep processes
are the most codified anywhere — more codified than any tech career,
because a single governing body publishes an official, versioned,
weighted blueprint. These are **not** wave-1/2 candidates; they are
recorded now because they stress different parts of the system, and the
adaptations they need should inform contract design before it ossifies.

## The five careers

| Career | Governing exam(s) | Official blueprint | Prep timeline | "Skills" shape |
|---|---|---|---|---|
| CPA (accounting) | Uniform CPA Exam: AUD/FAR/REG core + 1 of BAR/ISC/TCP (AICPA/NASBA) | https://www.aicpa-cima.com/resources/download/learn-what-is-tested-on-the-cpa-exam | 1,100–1,500 hrs total, 200–400/section, ~12–18 months serial | Area→Group→Topic hierarchy with weight ranges + representative task statements |
| CFA (finance) | CFA Levels I–III, strictly sequential (CFA Institute) | https://www.cfainstitute.org/programs/cfa-program/curriculum | ~300–400 hrs/level, 6 mo/level; ~4 yrs to charter | Topic areas whose weights shift by level; explicit level prerequisites |
| PMP (project mgmt) | PMP (PMI); adjacent CAPM, PMI-ACP | https://www.pmi.org/-/media/pmi/documents/public/pdf/certifications/new-pmp-examination-content-outline-2026.pdf | 100–200 study hrs over 8–12 wks + 35 mandatory contact hours | Domain→Task→Enabler (2026: People 33% / Process 41% / Business Env 26%) |
| Registered Nurse | NCLEX-RN (NCSBN, CAT adaptive) | https://www.ncsbn.org/publications/2026-nclex-rn-test-plan | 4–12 wks post-degree (commonly ~30 days, 2–3 hrs/day) | Client-needs categories with weights + the 6-step Clinical Judgment model |
| Bar exam (law) | UBE (MBE+MEE+MPT) + MPRE; NextGen bar from July 2026 (NCBE) | https://www.ncbex.org/exams · https://www.ncbex.org/exams/nextgen/content-scope | 8–10 wks full-time, 400–500 hrs | Fixed subject list + named lawyering skills; zero alias variation |

PMP is the natural first wave-3 candidate: shortest runway, largest
alias overlap with existing tracks (`agile`, `stakeholder management`,
`risk management` appear verbatim in tech PM postings), and the ECO is a
clean public PDF.

## Where the tech-built system fits beautifully

- **Closed official taxonomies.** Every blueprint is exactly what the
  `role_taxonomy` source type wants — official, complete, weighted,
  low-volatility (1–3-year revision cycles with announced effective
  dates). Better corpus anchors than anything in tech.
- **Coverage validation gets *stronger*.** Blueprint weights make
  proportional coverage checkable exactly ("plan hours per domain ∝
  published weight" is literally the standard NCLEX advice). The
  deterministic validation layer is the part of this product these
  careers reward most.
- **Known prep quanta.** 300 hrs/CFA level, 400–500 hrs bar, 8–12 wks
  PMP — scheduling constants the tech tracks never get to have.

## Where it strains — adaptations to design for

1. **Eligibility gates are not skills.** 150 credit hours (CPA), 35
   contact hours + experience audit (PMP), a nursing degree, a JD,
   sequential level passes (CFA). The taxonomy has no node type for
   "credential prerequisite," and the Planner must be able to *refuse to
   schedule around an unmet gate* rather than treat it as a weak spot.
   Likely shape: a new contract concept parallel to `SkillEntry`, checked
   by the deterministic prerequisite engine — which already exists and is
   exactly the right owner (axiom: prerequisites are computed
   deterministically).
2. **No alias culture → blueprint-version mapping instead.** Exam domains
   are canonical proper nouns ("FAR Area I", "Management of Care");
   lexical aliasing is nearly useless. What replaces it is **temporal
   aliasing across blueprint revisions** (2023 vs 2026 NCLEX plan; 2021 vs
   2026 PMP ECO; UBE vs NextGen). The taxonomy's append-only versioning
   already models this — but entry-level mapping between versions
   ("this v2 entry supersedes that v1 entry") is a new need.
3. **Exam windows are hard external deadlines.** Fixed test dates and
   result latencies replace "interview whenever ready." Good fit for a
   deterministic scheduler; new constraint *type* for it.
4. **Kind distribution collapses.** `concept` dominates almost totally;
   `tool` nearly empty (a financial calculator, IRC access); `language`/
   `framework` empty; `practice` maps to question-bank drilling and timed
   simulation. The kind system survives but must tolerate heavily skewed
   distributions — do not add validation that assumes kind balance.
5. **Corpus composition inverts.** Tech corpora lean on volatile
   third-party guides and postings; exam careers lean on a handful of
   official stable PDFs plus commercial prep providers whose material is
   aggressively copyrighted (BARBRI, UWorld, Becker — do not ingest).
   `interview_report` has no real equivalent; pass-rate statistics and
   score reports replace it. Manifest rule: official blueprints + free
   explainers only.

## Decision rule for entering wave 3

Do not start wave 3 until: (a) at least two wave-1 careers are live
end-to-end (enum → taxonomy → corpus → enrichment → eval), proving the
mechanics doc's checklist; and (b) the credential-prerequisite node type
has an accepted spec. Item (b) is the only genuinely new contract work in
this whole expansion — everything in waves 1–2 rides existing machinery.
