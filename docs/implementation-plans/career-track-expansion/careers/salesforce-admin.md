# Salesforce Administrator — Track Profile

**Proposed enum value:** `salesforce_admin` · **Wave 4** · Research grounded
2026-07-19.

## Track decision

Own track — the prep process is fully codified around a single vendor
credential with published section weights and a free official curriculum:
the Salesforce Certified Platform Administrator exam (refreshed 2025-12-15
— https://www.salesforceben.com/salesforce-platform-admin-exam-updated-for-2026-more-agentforce-less-configuration/)
plus the free ~60-hour "Prepare for Your Salesforce Administrator
Credential" Trailhead trailmix
(https://trailhead.salesforce.com/en/credentials/administrator). The skill
set is declarative platform configuration — objects, flows, the security
model, CRM app setup — with essentially zero overlap with any existing
track (no DS&A, no system design, no coding, no BI-tool stack). Raw
posting volume is modest next to the data tracks, but the exam pipeline is
the most codified of any Wave 4 candidate; that codification, not
ecosystem-hype numbers, is why the track ranks.

Honesty note on market size: vendor-ecosystem claims ("4.2M new jobs by
2024", later "9.3M by 2026" — IDC studies commissioned by Salesforce,
https://www.salesforce.com/news/press-releases/2021/09/20/idc-salesforce-economy-2021/)
count direct **and** indirect/induced jobs and have drawn analyst
skepticism for their jumps between editions
(https://www.techrepublic.com/article/idc-salesforce-economic-impact-study-makes-predictions-that-at-first-glance-seem-impossible/).
Do not cite them as demand evidence. Use posting trackers instead — see
Role snapshot.

**Resolver markers:** `"salesforce administrator"`, `"salesforce admin"`,
`"salesforce administration"`, `"sfdc admin"`, `"crm administrator"`,
`"crm admin"`, `"salesforce consultant"` (judgment call — junior
consultant prep is admin-cert-shaped), `"salesforce business analyst"`.
Precedence hazards: the tuple must be inserted **before** `data_analyst`
so `"salesforce business analyst"` does not fall through to the
`"business analyst"` marker. Markers are deliberately admin-keyed:
`"salesforce developer"` / `"salesforce engineer"` must **not** resolve
here (Apex/LWC prep is developer-shaped; today it falls through toward
`swe`, and a future `salesforce_developer` track would claim it).

## Role snapshot

Configures and maintains a company's Salesforce org: user and permission
management, data model changes (objects/fields), declarative automation
(Flow), reports and dashboards, data hygiene, and rollout of new features
— administration through clicks, not code
(https://admin.salesforce.com/salesforce-admin-skills-kit). No dedicated
BLS OOH occupation exists for the role, so demand evidence is
posting-tracker based: ~2,300 active US postings reference the
Salesforce Administrator credential specifically, trend climbing through
spring 2026, typical certified-admin salary ≈ $95k
(https://certdemand.com/guides/salesforce-admin-guide); ZipRecruiter
brackets the certified role at $75k–$155k
(https://www.ziprecruiter.com/Jobs/Salesforce-Certified-Administrator).
LinkedIn's "180,000+ Salesforce Certified Administrator jobs" figure is a
keyword-loose count (any posting mentioning Salesforce), not credential
demand — treat the ~2,300 credential-referencing number as the honest
floor and the loose count as ceiling noise.

## Prep-process profile

- **Exam pipeline (the dominant gate):** Salesforce Certified Platform
  Administrator — 60 scored questions + 5 unscored, 105 minutes, 65%
  passing score, $200 registration / $100 retake, no formal
  prerequisites (6+ months hands-on recommended)
  (https://certdemand.com/guides/salesforce-admin-guide). Published
  section weights, refreshed 2025-12-15: Configuration & Setup 15%,
  Object Manager & Lightning App Builder 15%, Sales & Marketing
  Applications 10%, Service & Support Applications 10%, Productivity &
  Collaboration 10%, Data & Analytics Management 17%, Automation 15%,
  Agentforce AI 8% (new section)
  (https://www.salesforceben.com/salesforce-platform-admin-exam-updated-for-2026-more-agentforce-less-configuration/,
  official rationale:
  https://admin.salesforce.com/blog/2026/what-the-salesforce-certified-platform-administrator-exam-update-means-for-admins).
  Note the shift: Data & Analytics is now the single largest section, and
  Configuration/Object Manager each dropped from 20% → 15%.
- **Interview loop (post-cert):** recruiter screen → hiring-manager
  conversation → scenario round (design a security model, debug a flow,
  "how would you handle this stakeholder request") → sometimes a hands-on
  org exercise or portfolio walkthrough of a Trailhead Playground /
  superbadge build
  (https://www.salesforceben.com/salesforce-admin-interview-questions/).
  The cert is a screen, not the finish line; interviews probe judgment on
  the same domains the exam weights.
- **Anchor resources:** the free official trailmix "Prepare for Your
  Salesforce Administrator Credential" (~60 hrs,
  https://trailhead.salesforce.com/en/credentials/administrator); the
  Admin Beginner trail
  (https://trailhead.salesforce.com/content/learn/trails/force_com_admin_beginner);
  the Salesforce Admin Skills Kit (official 14-skill role taxonomy,
  https://admin.salesforce.com/salesforce-admin-skills-kit); Salesforce
  Ben cert guide
  (https://www.salesforceben.com/salesforce-administrator-certification/).
  Study-hour estimates: 40–80 hrs
  (https://certdemand.com/guides/salesforce-admin-guide).
- **Typical 12-week arc:** org setup + navigation in a free Trailhead
  Playground → security model (profiles/permission sets, sharing) + data
  model (objects/fields/record types) → Sales & Service Cloud app
  configuration → Flow Builder + validation/formula logic → reports,
  dashboards, Data Loader hygiene → Agentforce basics + practice exams +
  scenario-interview mocks.

## Seed skill entries (draft)

### Existing entries — add `salesforce_admin` tag

From v1: `skill.agile` (2° — postings routinely ask for scrum-team
experience). From NEW·shared entries defined in `data-analyst.md`
(reconciliation to confirm the extra tag): `skill.stakeholder-communication`
(2° — admins are a stakeholder-facing role by definition),
`skill.data-quality` (2° — dedupe/hygiene is core admin work; its alias
`data validation` stays there, distinct from my `validation rules`),
`skill.excel` (2° — CSV prep for Data Loader), `skill.requirements-gathering`
(2° — turning vague asks into config), and `skill.dashboards` (2° —
**CONTESTED**, see alias notes; the bare `dashboards`/`reports`/`reporting`
aliases are homed there and this track never claims them).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.salesforce` | Salesforce Platform | `salesforce`, `salesforce platform`, `sfdc`, `salesforce crm`, `crm administration`, `lightning experience`, `salesforce lightning` | tool | salesforce_admin | Anchor entry; bare `crm` is CONTESTED (see alias notes). A future `salesforce_developer` track would co-tag |
| `skill.salesforce-data-model` | Objects & Fields (Data Model) | `custom objects`, `custom fields`, `object manager`, `record types`, `page layouts`, `schema builder` | concept | salesforce_admin | Object Manager section, 15% of exam |
| `skill.lightning-app-builder` | Lightning App Builder | `lightning app builder`, `lightning pages`, `lightning record pages`, `dynamic forms` | tool | salesforce_admin | Same exam section as data model |
| `skill.salesforce-flows` | Flow Builder & Process Automation | `salesforce flow`, `salesforce flows`, `flow builder`, `record-triggered flows`, `screen flows`, `process builder`, `workflow rules`, `approval processes`, `process automation` | tool | salesforce_admin | Automation section, 15%; legacy tool names kept because postings still use them. Bare `flows` deliberately not claimed |
| `skill.salesforce-security` | Salesforce Security Model | `permission sets`, `permission set groups`, `profiles and permission sets`, `salesforce profiles`, `role hierarchy`, `sharing rules`, `organization-wide defaults`, `owd`, `field-level security` | concept | salesforce_admin | The classic scenario-round topic; bare `profiles` deliberately not claimed (generic) |
| `skill.salesforce-users` | User & License Management | `user management`, `license management`, `salesforce licenses` | practice | salesforce_admin | `user provisioning` NOT claimed — IAM-flavored, belongs near `skill.iam` (devops-sre.md) |
| `skill.validation-rules` | Validation Rules | `validation rules`, `validation rule` | concept | salesforce_admin | Distinct from `data validation` (skill.data-quality) |
| `skill.formula-fields` | Formulas & Roll-Up Summaries | `formula fields`, `salesforce formulas`, `roll-up summary fields`, `cross-object formulas` | concept | salesforce_admin | Declarative logic short of Flow |
| `skill.salesforce-data-management` | Data Loader & Data Hygiene | `data loader`, `data import wizard`, `duplicate rules`, `duplicate management`, `mass data updates` | practice | salesforce_admin | Data & Analytics section (17%, now the largest) |
| `skill.soql` | SOQL & SOSL | `soql`, `sosl`, `salesforce object query language` | language | salesforce_admin | Admin-adjacent (reports/Data Loader exports); a future developer track co-tags |
| `skill.salesforce-reports` | Salesforce Reports & Dashboards | `salesforce reports`, `salesforce dashboards`, `salesforce reporting`, `report types`, `custom report types`, `report builder`, `joined reports` | tool | salesforce_admin | Never claims bare `reports`/`dashboards`/`reporting` — homed on `skill.dashboards` (data-analyst.md) |
| `skill.sales-cloud` | Sales Cloud | `sales cloud`, `opportunity management`, `sales process`, `salesforce campaigns`, `products and price books` | tool | salesforce_admin | 10% section; `campaign management` deliberately NOT claimed (digital-marketing-shaped); `lead management` ruled 2026-07-19 to `skill.crm` (digital-marketer.md) |
| `skill.service-cloud` | Service Cloud | `service cloud`, `case management`, `omni-channel`, `salesforce knowledge`, `assignment rules`, `escalation rules`, `email-to-case`, `web-to-case` | tool | salesforce_admin | 10% section; `case management` flagged in alias notes vs security tooling |
| `skill.sandboxes` | Sandboxes & Change Sets | `sandboxes`, `change sets`, `sandbox refresh`, `salesforce environments` | practice | salesforce_admin | Distinct from `sandbox analysis` (skill.malware-analysis, security-analyst.md) |
| `skill.agentforce` | Agentforce & Einstein Basics | `agentforce`, `salesforce einstein`, `einstein copilot`, `prompt builder` | tool | salesforce_admin | New 8% exam section (2025-12-15 refresh); `prompt builder` distinct from ai_engineer's `prompt engineering` |
| `skill.appexchange` | AppExchange & Packages | `appexchange`, `managed packages` | tool | salesforce_admin | Evaluate-and-install judgment |
| `skill.salesforce-collaboration` | Chatter & Productivity Tools | `chatter`, `salesforce chatter`, `quick actions`, `salesforce mobile app` | tool | salesforce_admin | Productivity & Collaboration section, 10%; smallest entry, kept because the exam sections it |

17 new + ~7 tagged ≈ 24 total for the track — far under the ~100 prompt
budget and under the ~55 self-cap.

**Optional / deferred** (add only on enrichment or user demand):
Experience Cloud, CPQ, Field Service, Marketing Cloud administration,
MuleSoft/integrations, Salesforce Shield, release/DevOps Center
management, Apex/LWC (developer-track material, not admin), Own/backup
tooling, Advanced Administrator (Platform Administrator II) as a distinct
concept set.

## Alias-collision & FTS5 notes

- **Never bare `reports`, `dashboards`, `reporting`** — homed on
  `skill.dashboards` (data-analyst.md, per 02-shared-entries ruling). This
  track uses `salesforce reports` / `salesforce dashboards` /
  `salesforce reporting` and requests a 2° `salesforce_admin` tag on
  `skill.dashboards` — listed as CONTESTED for the central pass.
- **`crm` (bare) — CONTESTED.** This track wants it on `skill.salesforce`
  (CRM administration *is* the job), but `digital_marketer` (parallel
  draft) plausibly wants it for CRM-marketing tooling. Claimed here only
  as `salesforce crm` + `crm administration`; the bare token awaits the
  central ruling. `salesforce` itself is homed here (confirmed against the
  parallel digital_marketer draft).
- **`salesforce` is a noisy FTS token in a vendor-heavy corpus** — prose
  mentions of the company (e.g. Tableau's owner) inflate counts. Treat
  the multi-word aliases (`flow builder`, `permission sets`) as the
  trustworthy enrichment signal, per the per-alias-count convention.
- **Short/noisy tokens:** `owd` (trust `organization-wide defaults`),
  `sfdc` (distinctive, fine), `chatter` (collides with ordinary English in
  prose — fine for résumé resolution, discount FTS counts).
- **Adjacency flags for the central pass:** `case management` (mine, on
  Service Cloud) vs security-analyst SOAR/ticketing — security-analyst.md
  claims `soar`/`security orchestration`, no collision today, but flag it;
  `process automation` (mine, on Flows) could attract RPA/business-analyst
  careers later; `user provisioning` deliberately not claimed (IAM);
  `lead management` (mine) vs a digital_marketer `lead generation` —
  boundary is CRM-ops vs demand-gen, no shared alias proposed.
- **Deliberately not claimed:** bare `flows` (UX has `user flows`; too
  generic), bare `profiles` (generic), bare `automation`, bare `crm` (see
  above), `campaign management`, `workflow orchestration` (homed on
  `skill.orchestration`, data-engineer.md), `email marketing` and
  anything demand-gen-shaped.
- Checked against v1 (166 entries): no proposed alias appears anywhere in
  `backend/taxonomy/skill_taxonomy_v1.json`; `data validation` /
  `model validation` / `output validation` near-misses are on other
  entries and none of my aliases collide with them.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://trailhead.salesforce.com/en/credentials/administrator | role_taxonomy | Official cert page + trailmix link; stable, occasional URL churn |
| https://trailhead.salesforce.com/en/credentials/administratoroverview | role_taxonomy | Credential overview (admin cert family); stable |
| https://trailhead.salesforce.com/content/learn/trails/force_com_admin_beginner | role_taxonomy | Free official Admin Beginner trail; canonical curriculum |
| https://admin.salesforce.com/salesforce-admin-skills-kit | role_taxonomy | Official 14-skill admin role taxonomy; the single best anchor doc |
| https://admin.salesforce.com/blog/2026/what-the-salesforce-certified-platform-administrator-exam-update-means-for-admins | role_taxonomy | Official rationale for the 2025-12-15 exam refresh |
| https://www.salesforceben.com/salesforce-administrator-certification/ | role_taxonomy | Community cert guide; refreshed regularly |
| https://www.salesforceben.com/salesforce-platform-admin-exam-updated-for-2026-more-agentforce-less-configuration/ | role_taxonomy | New section weights with old-vs-new comparison |
| https://certdemand.com/guides/salesforce-admin-guide | role_taxonomy | Posting counts + 6-week study plan; posting data volatile by design |
| https://www.salesforceben.com/salesforce-admin-interview-questions/ | interview_report | Interview-round question patterns |
| https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/ | role_taxonomy | Official SOQL/SOSL reference; stable, permissive dev-docs |
| https://www.reddit.com/r/salesforce/ (exam-experience threads, sampled) | interview_report | Real exam/interview experiences; volatile, sample per run |
| https://www.ziprecruiter.com/Jobs/Salesforce-Certified-Administrator | official_job_posting | Volatile; sample per run |
| (job boards: linkedin/indeed "salesforce administrator" searches) | official_job_posting | Volatile + login-gated; sample per run |

License note: anchor on Salesforce's own free properties (Trailhead,
admin.salesforce.com, developer docs) — never ingest paid prep vendors
(Focus on Force practice-exam class) even though they dominate search
results; same posture as the Wave 5 rule.

## Enrichment expectations

Expect `salesforce` (inflated — see FTS note), `flow builder`,
`permission sets`, `salesforce reports`, `sales cloud`, `service cloud`
to dominate counts. Zero-support flags likely for `quick actions`,
`joined reports`, `sandbox refresh`, `products and price books` (prose
phrasing varies) — keep them; résumé-resolution value stands on its own.
`agentforce` counts should grow fast in any 2026-fetched corpus; if they
don't, the manifest is missing current-cycle docs.

## Overlap with existing tracks

Near-zero overlap with all nine existing profiles and v1 — the only
shared entries are soft-skill/office-adjacent (`agile`, `excel`,
`stakeholder-communication`, `data-quality`, `requirements-gathering`,
contested `dashboards` 2°). Boundary with the parallel `digital_marketer`
draft: this track owns `salesforce` and CRM-ops vocabulary; marketing
automation, campaign management, and demand-gen vocabulary are theirs;
bare `crm` is the one genuinely contested token. A future
`salesforce_developer` track would co-tag `skill.salesforce` and
`skill.soql` and take Apex/LWC/platform-dev vocabulary; resolver markers
here are deliberately scoped so developer-titled roles do not resolve to
admin.
