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
