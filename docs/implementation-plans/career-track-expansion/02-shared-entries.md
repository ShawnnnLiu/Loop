# 02 · Shared-Entry Registry & Alias Homing Decisions

The taxonomy enforces **global alias uniqueness** — one alias resolves to
exactly one entry. Careers will land in separate increments, so without a
cross-career registry, the second career to land would collide with the
first (or silently duplicate a concept under a new id). This doc is that
registry. When implementing any career, check its NEW·shared rows here
first; create each shared entry once, tagged for all listed tracks, in
whichever increment lands first.

Track key: DA=data_analyst, DS=data_scientist, DE=data_engineer,
DO=devops_sre, CE=cloud_engineer, SA=security_analyst,
PM=product_manager, UX=ux_designer, ME=mobile_engineer. "(2°)" =
secondary tag — defensible, curation decides.

## NEW·shared entries (created once, defined in the noted profile)

| skill_id | defined in | tracks |
|---|---|---|
| `skill.iam` | devops-sre.md | DO, CE, SA |
| `skill.incident-response` | devops-sre.md | DO, SA |
| `skill.postmortems` | devops-sre.md | DO, SA(2°) — owns `rca`, `root cause analysis` |
| `skill.infrastructure-as-code` | devops-sre.md | DO, CE, DE(2°) |
| `skill.dns` | devops-sre.md | DO, CE — owns `route 53` |
| `skill.high-availability` | devops-sre.md | DO, CE |
| `skill.autoscaling` | devops-sre.md | DO, CE |
| `skill.disaster-recovery` | devops-sre.md | DO, CE |
| `skill.cost-optimization` | devops-sre.md | DO, CE |
| `skill.secrets-management` | devops-sre.md | DO, SA, CE(2°) |
| `skill.powershell` | devops-sre.md | DO, CE, SA |
| `skill.cloudformation` | devops-sre.md | DO, CE |
| `skill.devsecops` | devops-sre.md | DO, SA |
| `skill.deployment-strategies` | devops-sre.md | DO, ME(2°) — owns `feature flags` |
| `skill.cryptography` | cloud-engineer.md | CE, SA |
| `skill.compliance` | cloud-engineer.md | CE, SA |
| `skill.active-directory` | security-analyst.md | SA, CE — owns `kerberos`, `azure ad` |
| `skill.cloud-security` | security-analyst.md | SA, CE |
| `skill.s3` | data-engineer.md | DE, CE |
| `skill.databricks` | data-scientist.md | DS, DE |
| `skill.tableau` | data-analyst.md | DA, DS |
| `skill.power-bi` | data-analyst.md | DA, DS(2°) |
| `skill.data-visualization` | data-analyst.md | DA, DS |
| `skill.hypothesis-testing` | data-analyst.md | DA, DS |
| `skill.eda` | data-analyst.md | DA, DS |
| `skill.data-cleaning` | data-analyst.md | DA, DS, DE(2°) |
| `skill.window-functions` | data-analyst.md | DA, DS, DE |
| `skill.metric-definition` | data-analyst.md | DA, DS, PM — owns `north star metric` |
| `skill.cohort-funnel-analysis` | data-analyst.md | DA, DS, PM |
| `skill.data-storytelling` | data-analyst.md | DA, DS, PM |
| `skill.stakeholder-communication` | data-analyst.md | DA, DS, PM, UX(2°) |
| `skill.data-quality` | data-analyst.md | DA, DE — owns bare `data quality` |
| `skill.google-analytics` | data-analyst.md | DA, PM |
| `skill.regression-analysis` | data-analyst.md | DA, DS |
| `skill.matplotlib` | data-scientist.md | DS, DA |
| `skill.experiment-design` | data-scientist.md | DS, PM — owns `experimentation` |
| `skill.product-sense` | data-scientist.md | DS, PM, UX |
| `skill.data-warehousing` | data-engineer.md | DE, DA |
| `skill.dimensional-modeling` | data-engineer.md | DE, DA |
| `skill.user-research` | product-manager.md | PM, UX |
| `skill.figma` | ux-designer.md | UX, PM |
| `skill.user-flows` | ux-designer.md | UX, PM |
| `skill.platform-guidelines` | ux-designer.md | UX, ME |
| `skill.accessibility` | ux-designer.md | UX, ME(2°), swe(2°) |

## Contested aliases — single-home rulings

Tokens more than one career wanted; the ruling keeps resolution
unambiguous. Changing a ruling = update every profile that references it.

| alias | home | losers / rationale |
|---|---|---|
| `experimentation`, `experiment design` | `skill.experiment-design` (new) | not `skill.ab-testing`; a/b keeps `a/b testing`, `ab testing`, `split testing` |
| `root cause analysis`, `rca` | `skill.postmortems` (new) | not cloud `skill.troubleshooting` |
| `alert tuning`, `detection rules` | `skill.detection-engineering` (new, SA) | not devops observability entries |
| `monitoring`, `logging`, `observability` | `skill.observability` (v1) | every ops-flavored track tags it instead |
| `security` (bare) | `skill.application-security` (v1) | SA tags the entry; bare token unwinnable anyway |
| `aws lambda`, `serverless` | `skill.serverless` (v1) | CE/DO tag it |
| `etl`, `data pipelines` | `skill.data-pipelines` (v1) | DE/DA tag it; consider adding `elt` |
| `data modeling` | `skill.database-design` (v1) | warehouse-specific forms live on new `skill.dimensional-modeling` |
| `time series`, `forecasting` | `skill.time-series` (v1) | DA/DS tag it |
| `agile`, `scrum` | `skill.agile` (v1) | PM/DA/UX tag it |
| `oauth`, `oauth2`, `authorization` | `skill.authentication` (v1) | `kerberos` deliberately NOT here — it lives on `skill.active-directory` |
| `spreadsheets` | `skill.excel` (new) | not google-sheets |
| `feature flags` | `skill.deployment-strategies` (new, DO) | not mobile release entry |
| `dashboards` | `skill.dashboards` (new, DA) | not grafana (v1 grafana has only `grafana`) |

## Deliberately homeless tokens

Too ambiguous to resolve to one skill; never make these aliases:

`playbooks` (ansible/soar/runbooks three-way) · `documentation` ·
`pii` (bare) · `vpn` (bare) · `async/await` · `compose` (docker vs
jetpack) · `room` (bare) · `junit` · `sync` · `persistence` (bare) ·
`ransomware` (bare) · `portfolio` (bare) · `star` (bare) · `triage`-like
generics are allowed only where the profile explicitly flags the FTS
noise.

## Alias additions to existing v1 entries (curation-review suggestions)

New-version edits to existing entries, harvested from the research; all
optional, none load-bearing:

- `skill.model-evaluation` += `cross-validation`, `cross validation`
- `skill.statistics` += `descriptive statistics`
- `skill.jupyter` += `google colab`, `colab`
- `skill.ab-testing` += `split testing`
- `skill.concurrency` += `gcd`, `grand central dispatch`
- `skill.git` += `version control`
- `skill.kubernetes` += consider `eks`, `gke`, `aks` (provider flavors)

## Per-track size tally (draft estimate, against the ~100 prompt budget)

| track | existing tagged | new entries (incl. shared) | ~total |
|---|---|---|---|
| data_analyst | ~13 | ~22 | ~35 |
| data_scientist | ~30 | ~26 | ~56 |
| data_engineer | ~35 | ~20 | ~55 |
| devops_sre | ~34 | ~24 | ~58 |
| cloud_engineer | ~20 | ~26 | ~46 |
| security_analyst | ~8 | ~35 | ~43 |
| product_manager | ~6 | ~24 | ~30 |
| ux_designer | ~2 | ~23 | ~25 |
| mobile_engineer | ~20 | ~33 | ~53 |

All comfortably under the ~100/track prompt-slice bound. Total new
entries across all nine careers ≈ 150–170 (shared entries counted once),
roughly doubling the 166-entry v1 file — well within reason for a curated
JSON reviewed career-by-career, not all at once.

---

# Wave 4–5 additions (research pass 2026-07-19)

Fifteen further careers were profiled 2026-07-19 (see README roadmap).
Extended track key: IT=it_support, DM=digital_marketer,
MC=management_consultant, BA=business_analyst, NE=network_engineer,
HR=hr_specialist, FA=financial_analyst, SF=salesforce_admin,
TK=teacher_k12, RE=real_estate_agent, FV=financial_advisor,
IA=insurance_agent, AC=actuary, MD=medical_coder, EL=electrician.

## NEW·shared entries (wave 4–5; created once, defined in the noted profile)

| skill_id | defined in | tracks |
|---|---|---|
| `skill.powerpoint` | financial-analyst.md | FA, MC — owns `powerpoint`, `ppt`, `pitch deck`; MC slide-writing keeps `slide writing`/`slide decks`/`storylining` |
| `skill.vba` | financial-analyst.md | FA, AC (DA 2° later on demand) |
| `skill.mergers-acquisitions` | management-consultant.md | MC, FA — owns `m&a`, `mergers and acquisitions`, `due diligence`; FA merger-models keeps `merger model`/`accretion dilution` |
| `skill.process-improvement` | business-analyst.md | BA, MC — owns `process improvement`, `lean six sigma`, `six sigma`, `operations improvement`, `operational efficiency` (absorbed MC's operations-improvement mint) |
| `skill.change-management` | management-consultant.md | MC, HR — owns bare `change management`; it_support `skill.itil` keeps ITIL 4's `change enablement` |
| `skill.client-management` | management-consultant.md | MC, FV, IA, RE(2°) — owns `client relationship management`, `client relationships`, `client retention`, `book of business`, `policy renewals`, `engagement management`, `workstream management` |
| `skill.prospecting` | financial-advisor.md | FV, IA, RE — owns `prospecting`, `lead generation`, `lead gen`, `cold calling`, `client acquisition`, `sphere of influence` |
| `skill.exam-simulation` | financial-advisor.md | FV, TK, RE, IA, AC, MD, EL — the ONE universal exam-practice entry (`practice exams`, `practice tests`, `mock exams`, `question banks`, `timed practice`, `test-taking strategies`); wave-3 careers (cpa/cfa/pmp/nclex/bar) tag it when they land |
| `skill.consultative-selling` | insurance-agent.md | IA, FV(2°), RE(2°) |
| `skill.negotiation` | real-estate-agent.md | RE, IA(2°), FV(2°) — HR keeps only long forms (`offer negotiation`, `salary negotiation`) on offer-management |
| `skill.annuities` | insurance-agent.md | IA, AC, FV(2°) — absorbed actuary's mint (`annuity valuation`) |
| `skill.series-6-63` | insurance-agent.md | IA, FV(2°) |
| `skill.sie-exam`, `skill.series-7` | financial-advisor.md | FV, IA(2°) — the insurance variable-line FINRA stack |
| `skill.crm` | digital-marketer.md | DM, IA(2°), FV(2°) — owns `crm`, `customer relationship management`, `lead management`; optional alias candidate `redtail` |
| `skill.hubspot` | digital-marketer.md | DM, IA(2°) |
| `skill.salesforce` | salesforce-admin.md | SF, IA(2°) — owns `salesforce`, `sfdc`; a future salesforce_developer co-tags |
| `skill.firewalls` | network-engineer.md | NE, SA(2°) — owns `firewalls`, `acls`, `palo alto`, `fortinet` (SA had deferred the vendor names) |
| `skill.confluence` | business-analyst.md | BA, PM(2°) |
| `skill.hipaa-privacy` | medical-coder.md | MD — owns bare `hipaa` (ruling change, see below) |
| `skill.virtualization` | it-support.md | IT (CE tag is a curation call) |
| `skill.wireless`, `skill.network-services`, `skill.network-labs` | network-engineer.md | NE (IT tags these rather than minting; `dhcp` lives on network-services) |

## Wave 4–5 single-home rulings (contested tokens)

| alias | home | losers / rationale |
|---|---|---|
| `business analyst` (resolver marker, not alias) | `business_analyst` track | Re-homed from data_analyst (data-analyst.md marker list updated); BA tuple precedes DA's; salesforce_admin's `salesforce business analyst` precedes BA; DA keeps `business intelligence`/`bi analyst`; MC's McKinsey "Business Analyst" title noted but not marked |
| `lead generation`, `lead gen` | `skill.prospecting` (FV) | not DM `skill.demand-generation` (keeps `demand generation`/`demand gen`/`growth marketing`/`growth hacking`) |
| `lead nurturing`, `lead scoring` | DM `skill.marketing-automation` | not the sales cluster |
| `lead management` | DM `skill.crm` | not SF `skill.sales-cloud` |
| `change management` | `skill.change-management` (MC+HR) | not IT `skill.itil` (keeps `change enablement`) |
| `process improvement`, `lean six sigma` | `skill.process-improvement` (BA+MC) | MC operations-improvement folded in |
| `client relationship management`, `book of business` | `skill.client-management` (MC) | IA/FV client entries folded in |
| `powerpoint`, `ppt` | FA `skill.powerpoint` | not MC slide-writing |
| `m&a`, `mergers and acquisitions`, `due diligence` | MC `skill.mergers-acquisitions` | not FA merger-models |
| `time value of money` | FA `skill.corporate-finance` | not AC financial-mathematics (keeps `interest theory`/`exam fm`) |
| `annuities` family | IA `skill.annuities` / `skill.variable-products` / `skill.health-insurance` | FV insurance-planning stripped to `insurance planning`/`insurance products` + 2° tags; AC folded in |
| `series 7`, `securities industry essentials` | FV per-exam entries | IA finra-licensing replaced by `skill.series-6-63` |
| `medicare`, `medicaid` | MD `skill.medicare-payer-rules` | IA social-insurance-programs keeps `social security benefits` (FV's `social security` is a distinct string — allowed) |
| `hipaa`, `hipaa compliance` | MD `skill.hipaa-privacy` | **RULING CHANGE** to the wave-1/2 table: `hipaa` removed from `skill.compliance` (cloud-engineer.md updated in the same pass; compliance gains MD tag and keeps `pci dss`/`soc 2`/`fedramp`/`grc`) |
| `reading comprehension` | EL `skill.reading-comprehension` (aptitude-test blueprint section) | TK literacy-instruction keeps `phonics`/`science of reading` |
| `dhcp` | NE `skill.network-services` | not an alias-add to v1 `skill.networking` (IT proposal withdrawn) |
| `subnetting`, `cidr` | CE `skill.cloud-networking` (unchanged wave-2 home) | NE documents the tension, does not claim |
| `network troubleshooting` | proposed alias-add to v1 `skill.networking` | not `skill.troubleshooting` (NE's alternative proposal superseded) |
| `salesforce` | SF `skill.salesforce` | DM and the sales careers use `skill.crm`/`skill.hubspot` |
| `wireshark` | promote SA's `skill.wireshark` to NEW·shared SA+NE | was minted SA-only in security-analyst.md |

## Deliberately homeless — wave 4–5 additions

Adding to the standing list: `assessment` (teacher vs security vs UX vs
exam meanings) · `contracts` (real-estate vs paralegal vs procurement) ·
`coding` (medical vs software — catastrophic) · `encoder` (medical
software vs transformers) · `epic` (EHR vs agile) · `macros` ·
`interviewing` · `training` · `transformation` · `lean` · `prophet`
(actuarial software vs forecasting library) · `risk management` (bare —
reserved unassigned until the wave-3 PMP/CFA drafts land) ·
`public speaking` (pending a ruling when a second claimant lands) ·
`customer journey` (UX vs marketing — unresolved, neither claims).

## Alias additions to existing entries (curation-review suggestions)

- `skill.authentication` += `mfa`, `multi-factor authentication` (IT)
- `skill.networking` += `osi model`, `network fundamentals`,
  `network troubleshooting` (IT+NE convergent proposals)
- `skill.load-balancing` += `f5`, `big-ip` (NE)
- `skill.market-sizing` += `guesstimates` (MC)
- `skill.probability` += `exam p`, `probability theory` (AC)
- `skill.statistics` += `mathematical statistics` (AC)
- `skill.requirements-gathering` (data-analyst.md) — promote to
  NEW·shared DA+BA (+SF 2°); suggest alias `stakeholder analysis` on
  `skill.stakeholder-communication` (BA)
- `skill.database-design` += `erd`, `entity relationship diagram` (BA)
- `skill.crm` += `redtail` (FV; optional)

Widely tagged wave-1/2 shared entries (curation confirms each 2°):
`skill.excel` (MC, FA, FV, HR, AC, SF 2°, DM), `skill.stakeholder-communication`
(nearly all 15), `skill.dashboards` (DM, SF 2°), `skill.agile` (BA, SF 2°).

## Per-track size tally — wave 4–5 (draft, post-reconciliation)

| track | new entries (shared counted at defining track) | ~total incl. tags |
|---|---|---|
| it_support | ~15 | ~28 |
| digital_marketer | ~28 | ~36 |
| management_consultant | ~16 | ~24 |
| business_analyst | ~13 | ~23 |
| network_engineer | ~14 | ~27 |
| hr_specialist | ~19 | ~22 |
| financial_analyst | ~23 | ~30 |
| salesforce_admin | ~17 | ~23 |
| teacher_k12 | ~25 | ~26 |
| real_estate_agent | ~16 | ~20 |
| financial_advisor | ~20 | ~30 |
| insurance_agent | ~16 | ~25 |
| actuary | ~15 | ~27 |
| medical_coder | ~20 | ~22 |
| electrician | ~20 | ~20 |

All far under the ~100/track prompt budget. Total new entries across the
fifteen ≈ 270–280 (shared counted once) — landing career-by-career, one
taxonomy version each, per the mechanics doc.
