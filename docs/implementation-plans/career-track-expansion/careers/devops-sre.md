# DevOps / SRE / Platform Engineer — Track Profile

**Proposed enum value:** `devops_sre` · **Wave 1** · Research grounded
2026-07-06 (sources inline; posting/salary figures are point-in-time).

## Track decision

One track, three title flavors. roadmap.sh maintains a single roadmap
titled "DevOps Engineer or SRE" (https://roadmap.sh/devops); GitLab treats
DevOps / SRE / platform engineer as sibling emphases on one skill base
(https://about.gitlab.com/blog/career-spotlight-sre-vs-devops-engineer-vs-devops-platform-engineer/);
multiple 2025 analyses document "Platform Engineer" postings as rebranded
DevOps postings with near-identical requirements
(https://www.infoworld.com/article/4037775/devops-sre-and-platform-engineering-whats-the-difference.html).
The flavors differ in posting emphasis, not skill base: DevOps → ci/cd and
automation; SRE → SLOs, error budgets, incident response; platform →
internal developer platforms, Backstage, golden paths. Splitting them would
triple curation cost for near-identical vocabularies (see granularity
policy in `../01-expansion-mechanics.md`).

**Resolver markers** (`_TRACK_MARKERS`, insert before `swe` — "devops
engineer" and "site reliability engineer" must not fall through to swe):
`"devops"`, `"dev ops"`, `"sre"`, `"site reliability"`,
`"platform engineer"`, `"platform engineering"`, `"infrastructure engineer"`,
`"release engineer"`, `"build engineer"`.

## Role snapshot

Automates the software delivery lifecycle — CI/CD, infrastructure-as-code,
containers, cloud environments, monitoring — sitting between development
and operations (https://roadmap.sh/devops). Demand: 12k+ US "DevOps
Engineer" LinkedIn postings, ~9.7k on Indeed; Stack Overflow 2024 found
SRE/cloud-infra the highest-paid developer roles (SRE median $166.5k,
https://survey.stackoverflow.co/2024/). Prep is well-codified and
cert-anchored, though 2025 posting analyses show cert *mentions* declining
in favor of practical assessment
(https://devopsprojectshq.com/role/devops-market-h2-2025/).

## Prep-process profile

What a study plan for this track schedules — the Strategist/Planner-facing
shape:

- **Anchor certifications** (each has an official public syllabus — prime
  `role_taxonomy` corpus material):
  - CKA (performance-based, live cluster): Troubleshooting 30%, Cluster
    Architecture 25%, Services & Networking 20%, Workloads & Scheduling
    15%, Storage 10%
    (https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/).
  - HashiCorp Terraform Associate: IaC concepts, CLI workflow, modules,
    state/backends
    (https://developer.hashicorp.com/terraform/tutorials/certification-004/associate-review-004).
  - AWS DevOps Engineer Professional (DOP-C02): SDLC Automation 22%,
    Config Mgmt & IaC 17%, Security 17%, Resilience 15%, Monitoring 15%,
    Incident Response 14%
    (https://docs.aws.amazon.com/aws-certification/latest/examguides/devops-engineer-professional-02.html).
- **Interview loop** (documented for Google SRE; generalizes): coding/
  scripting screen → Linux internals & troubleshooting round → systems
  design (NALSD flavor: capacity math, failure modes, monitoring) →
  behavioral (https://igotanoffer.com/blogs/tech/google-site-reliability-engineer-interview).
  Non-FAANG loops often substitute a take-home (build a pipeline,
  containerize an app, Terraform a module); the de facto community prep
  bank is https://github.com/bregman-arie/devops-exercises (2,371
  exercises).
- **Typical 12-week arc:** Linux+shell+git → networking + one cloud →
  Docker + CI/CD build → Kubernetes labs → Terraform + Ansible →
  monitoring/SLOs/incident scenarios + mocks (https://roadmap.sh/devops,
  https://github.com/MichaelCade/90DaysOfDevOps).

## Seed skill entries (draft for the next taxonomy version)

Status column: **EXISTING** = entry already in `skill_taxonomy_v1.json`;
the change is adding `devops_sre` to its `track_tags`. **NEW** = new
`SkillEntry`. **NEW·shared** = new entry proposed by more than one career
profile — create once, tag all listed tracks (cross-referenced in
`../02-shared-entries.md`). All aliases lowercase-normalized. Draft for
human curation review — the review is the gate.

### Existing entries — add `devops_sre` tag (~30)

`skill.python`, `skill.bash`, `skill.go`, `skill.sql`, `skill.kubernetes`
(consider adding aliases `k8s` already present; `eks`/`gke`/`aks` are a
curation call — provider-managed flavors), `skill.docker`,
`skill.terraform`, `skill.git`, `skill.github-actions`, `skill.jenkins`,
`skill.linux`, `skill.nginx`, `skill.prometheus`, `skill.grafana`,
`skill.datadog`, `skill.ci-cd`, `skill.aws`, `skill.gcp`, `skill.azure`,
`skill.networking`, `skill.load-balancing`, `skill.distributed-systems`,
`skill.microservices`, `skill.kafka`, `skill.elasticsearch`,
`skill.system-design`, `skill.observability`, `skill.serverless`,
`skill.message-queues`, `skill.caching`, `skill.event-driven`,
`skill.code-review`, `skill.debugging`, `skill.agile`.

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.helm` | Helm | `helm`, `helm charts` | tool | devops_sre | Standard k8s packaging; core in postings |
| `skill.ansible` | Ansible | `ansible`, `configuration management` | tool | devops_sre | Config-management standard |
| `skill.gitops` | GitOps | `gitops`, `argocd`, `argo cd`, `flux` | practice | devops_sre | Declarative k8s delivery; platform staple |
| `skill.infrastructure-as-code` | Infrastructure as Code | `infrastructure as code`, `iac` | concept | devops_sre, cloud_engineer | 17% of DOP-C02; NEW·shared |
| `skill.slo-sli` | SLOs & Error Budgets | `slo`, `sli`, `error budget`, `service level objectives` | concept | devops_sre | The SRE-defining concept (Google SRE book) |
| `skill.incident-response` | Incident Response | `incident response`, `incident management`, `on-call`, `incident handling` | practice | devops_sre, security_analyst | NEW·shared; ops vs security flavor differ, alias space is one |
| `skill.postmortems` | Blameless Postmortems | `postmortem`, `postmortems`, `blameless postmortem`, `root cause analysis`, `rca` | practice | devops_sre | SRE book ch. 15 canon |
| `skill.deployment-strategies` | Deployment Strategies | `blue-green deployment`, `blue/green deployment`, `canary deployment`, `canary release`, `rolling deployment`, `feature flags` | concept | devops_sre | Asked in nearly every pipeline interview |
| `skill.dns` | DNS | `dns`, `dns resolution`, `route 53`, `route53` | concept | devops_sre, cloud_engineer | NEW·shared; #1 real-world outage cause |
| `skill.high-availability` | High Availability | `high availability`, `fault tolerance`, `multi-az`, `redundancy` | concept | devops_sre, cloud_engineer | NEW·shared; 15% of DOP-C02, 26% of SAA-C03 |
| `skill.autoscaling` | Autoscaling & Capacity Planning | `autoscaling`, `auto scaling`, `capacity planning` | concept | devops_sre, cloud_engineer | NEW·shared; NALSD interview material |
| `skill.disaster-recovery` | Disaster Recovery | `disaster recovery`, `rto`, `rpo`, `backup and restore` | concept | devops_sre, cloud_engineer | NEW·shared |
| `skill.cost-optimization` | Cloud Cost Optimization | `cost optimization`, `finops`, `rightsizing` | practice | devops_sre, cloud_engineer | NEW·shared; rising posting keyword |
| `skill.secrets-management` | Secrets Management | `secrets management`, `hashicorp vault`, `vault`, `credential rotation` | tool | devops_sre, security_analyst | NEW·shared |
| `skill.iam` | Identity & Access Management | `iam`, `identity and access management`, `least privilege`, `rbac` | concept | devops_sre, cloud_engineer, security_analyst | NEW·shared; top-weighted across cert tracks |
| `skill.powershell` | PowerShell | `powershell`, `pwsh` | language | devops_sre, cloud_engineer, security_analyst | NEW·shared; Windows-shop automation |
| `skill.gitlab-ci` | GitLab CI | `gitlab ci`, `gitlab ci/cd`, `gitlab` | tool | devops_sre | Common CI alternative |
| `skill.cloudformation` | CloudFormation | `cloudformation`, `cfn` | tool | devops_sre, cloud_engineer | NEW·shared; AWS-native IaC |
| `skill.service-mesh` | Service Mesh | `service mesh`, `istio`, `linkerd` | framework | devops_sre | Platform-scale traffic/mTLS; secondary |
| `skill.opentelemetry` | OpenTelemetry | `opentelemetry`, `otel` | framework | devops_sre | Emerging observability standard; secondary |
| `skill.backstage` | Backstage / Internal Developer Portals | `backstage`, `internal developer platform`, `internal developer portal` | tool | devops_sre | Signature platform-engineer tool; secondary |
| `skill.chaos-engineering` | Chaos Engineering | `chaos engineering`, `fault injection` | practice | devops_sre | SRE-flavor differentiator; secondary |
| `skill.devsecops` | DevSecOps | `devsecops`, `shift left`, `sast`, `dast` | practice | devops_sre, security_analyst | NEW·shared; rising in postings |
| `skill.runbooks` | Runbooks | `runbooks`, `runbook` | practice | devops_sre | Operational-maturity signal |

Deliberately **excluded**: `yaml`/`json`/`hcl` (markup, not skills a plan
schedules — HCL competence is `skill.terraform`); `groovy`/`packer`
(too niche for the ≤100 budget); certs themselves (prep resources, not
skills — they live in the corpus, not the taxonomy).

## Alias-collision & FTS5 notes

- `"aws lambda"` already resolves to `skill.serverless` (v1) — do not
  re-home it.
- `"monitoring"`, `"logging"` live on `skill.observability` — the new
  observability-adjacent entries above deliberately avoid both.
- `"playbooks"` is left out entirely: three-way ambiguity (Ansible
  playbooks / SOAR playbooks / runbooks) makes it unresolvable.
- `"alert tuning"` / `"detection rules"` are assigned to the security
  track's `skill.detection-engineering` (one home only).
- FTS5 noise: `go` (existing), `sre`, `iac`, `dns` are short tokens; `dns`
  and `iac` are distinctive enough in tech prose, but treat `go` counts as
  unusable and rely on `golang` (see `../01-expansion-mechanics.md`).

## Candidate corpus sources (manifest seeds)

Target 30–60 docs; this seeds the stable core. Types are expected
`SourceType` values — the deterministic classifier has final say.

| URL | expected type | license / volatility note |
|---|---|---|
| https://roadmap.sh/devops | role_taxonomy | Canonical community role guide ("DevOps Engineer or SRE"); stable |
| https://roadmap.sh/devops/skills | role_taxonomy | Skill-by-skill companion; stable |
| https://sre.google/sre-book/table-of-contents/ | role_taxonomy | Google SRE book, full text, **CC-BY-4.0** — ideal licensing |
| https://sre.google/workbook/table-of-contents/ | role_taxonomy | SRE Workbook incl. NALSD; CC-BY-4.0 |
| https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/ | role_taxonomy | Official CKA domains/weights; revs ~yearly with k8s versions |
| https://developer.hashicorp.com/terraform/tutorials/certification-004/associate-review-004 | role_taxonomy | Official Terraform Associate content; URL changes on exam rev |
| https://docs.aws.amazon.com/aws-certification/latest/examguides/devops-engineer-professional-02.html | role_taxonomy | Official DOP-C02 guide; ~3-yr rev cycle |
| https://github.com/bregman-arie/devops-exercises | interview_report | 2,371 community exercises; check repo license before snapshot |
| https://github.com/mxssl/sre-interview-prep-guide | interview_report | Structured SRE loop prep |
| https://igotanoffer.com/blogs/tech/google-site-reliability-engineer-interview | interview_report | Google SRE loop anatomy; commercial, moderately volatile |
| https://github.com/MichaelCade/90DaysOfDevOps | role_taxonomy | 90-day structured learning map |
| https://netflixtechblog.com/ | company_engineering_blog | Reliability/chaos/platform posts |
| https://aws.amazon.com/blogs/architecture/ | company_engineering_blog | Reference architectures for design-interview prep |
| (job boards: linkedin/indeed devops searches) | official_job_posting | **Highly volatile** (45-day prior) + ToS restrictions; sample per ingestion run, don't treat as durable |

## Enrichment expectations

- High-count aliases to expect: `kubernetes`, `docker`, `terraform`,
  `ci/cd`, `ansible`, `linux`, `prometheus` — all appear in posting
  analyses at 25–50% of postings
  (https://scale.jobs/blog/devops-job-market-trends).
- Likely zero/low-support flags that are *fine to keep*: `backstage`,
  `chaos engineering`, `opentelemetry` (young/niche; corpus thin).
- If `slo`/`error budget` come back zero, the corpus is missing SRE-book
  chapters — fix the manifest, not the entry.

## Overlap with existing tracks

High overlap with `swe` on the propose side (Python/Go, git, code review,
system design — Google hires SRE on a shared coding bar); distinctive:
Linux internals, networking, IaC, k8s operations, on-call/incident
practice. ~34 of ~55 entries are shared with existing tracks — this career
is cheap to add because `swe` already paid for its foundation.
