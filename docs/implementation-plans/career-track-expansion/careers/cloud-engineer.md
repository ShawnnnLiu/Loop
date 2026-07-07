# Cloud Engineer — Track Profile

**Proposed enum value:** `cloud_engineer` · **Wave 2** (see note) ·
Research grounded 2026-07-06.

## Track decision

Own track, second wave. The DevOps overlap is famously large (~60% of the
skill graph: terraform, docker/k8s, ci/cd, monitoring, python/bash), and
blended "cloud devops engineer" postings are common — but the prep spines
differ: cloud-engineer hiring is the most certification-defined in tech
(SAA-C03 / AZ-104 / GCP ACE, each with an official public exam guide),
and its interview center is provider-service troubleshooting and
architecture ("ec2 unreachable — walk me through it") rather than
pipeline/reliability. Posting language splits the same way: cloud postings
lead with provider services and architecture; devops postings lead with
delivery process (https://www.indeed.com/career-advice/finding-a-job/devops-engineer-vs-cloud-engineer).
Title volume also differs sharply: 82k+ US "cloud engineer" vs 12k
"devops engineer" LinkedIn postings — cloud engineer is the broader
umbrella title.

**Why wave 2 anyway:** `devops_sre` (wave 1) already lands most of the
shared vocabulary; adding `cloud_engineer` afterward is mostly track-tag
additions plus ~15 new provider-service entries, and the corpus can reuse
the same cert-syllabus source class. Cheap to add once devops exists;
expensive to distinguish if added simultaneously.

**Resolver markers** (insert before `devops_sre` if its markers could
absorb these — check at implementation): `"cloud engineer"`,
`"cloud engineering"`, `"cloud architect"`, `"solutions architect"`,
`"cloud administrator"`, `"cloud infrastructure"`, `"aws engineer"`,
`"azure engineer"`.

## Role snapshot

Designs, builds, secures, and operates infrastructure on AWS/Azure/GCP —
compute/storage/network provisioning, IAM, cost/reliability optimization.
82k+ US LinkedIn postings, ~85k on Glassdoor; ~30% YoY growth reported for
cloud-computing jobs. The most certification-defined career in tech.

## Prep-process profile

- **Anchor certifications** (official syllabi = prime corpus):
  - AWS Solutions Architect Associate (SAA-C03): Secure 30%, Resilient
    26%, High-Performing 24%, Cost-Optimized 20%
    (https://docs.aws.amazon.com/aws-certification/latest/examguides/solutions-architect-associate-03.html).
  - AWS Cloud Practitioner (CLF-C02) as on-ramp.
  - Microsoft AZ-104: Identities & Governance 20–25%, Compute 20–25%,
    Storage 15–20%, Networking 15–20%, Monitoring 10–15%
    (https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-104).
  - Google Associate Cloud Engineer (official exam guide PDF).
  - Secondary: CompTIA Cloud+, Terraform Associate (shared with devops).
- **Interview loop** (rich documentation for AWS cloud roles): recruiter →
  technical phone screen (tcp/ip, dns, cidr/subnetting, security groups vs
  nacls, iam) → onsite scenario troubleshooting ("ec2 unreachable",
  "s3 access denied", "rds slow") + small-scale architecture design
  (https://prepfully.com/interview-guides/aws-cloud-support-engineer).
- **Typical 12-week arc:** cloud fundamentals + billing → SAA-C03 domains
  + practice exams (Tutorials Dojo is the de facto bank) → hands-on
  portfolio via the **Cloud Resume Challenge** (16 steps: static site +
  dns + cdn + serverless api + iac + ci/cd — the community-standard
  cert-to-job bridge, https://cloudresumechallenge.dev/docs/the-challenge/)
  → scenario drills + mocks.

## Seed skill entries (draft)

### Existing entries — add `cloud_engineer` tag (~20)

`skill.aws`, `skill.azure`, `skill.gcp`, `skill.python`, `skill.bash`,
`skill.sql`, `skill.go`, `skill.linux`, `skill.git`, `skill.docker`,
`skill.kubernetes`, `skill.terraform`, `skill.serverless` (owns
`aws lambda`), `skill.networking`, `skill.load-balancing`,
`skill.dynamodb`, `skill.ci-cd`, `skill.observability`,
`skill.system-design`, `skill.github-actions`.

### New entries (beyond the NEW·shared set landed with `devops_sre`)

Shared entries from `devops-sre.md` that tag `cloud_engineer`:
`skill.iam`, `skill.infrastructure-as-code`, `skill.dns` (owns
`route 53`), `skill.high-availability`, `skill.autoscaling`,
`skill.disaster-recovery`, `skill.cost-optimization`,
`skill.cloudformation`, `skill.powershell`, `skill.secrets-management`
(secondary). Plus `skill.s3` from `data-engineer.md`.

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.ec2` | EC2 & Cloud Compute | `ec2`, `elastic compute cloud`, `compute engine`, `azure vms` | tool | cloud_engineer | Foundational compute across providers; bundling is a curation call |
| `skill.cloud-networking` | Cloud Networking (VPC) | `vpc`, `subnetting`, `cidr`, `security groups`, `vpc peering`, `transit gateway` | concept | cloud_engineer | The hardest-tested SAA area; phone-screen staple |
| `skill.cloudwatch` | CloudWatch & Cloud Monitoring | `cloudwatch`, `azure monitor`, `cloud logging` | tool | cloud_engineer | Troubleshooting starts at metrics/logs |
| `skill.rds` | Managed Relational Databases | `rds`, `aurora`, `cloud sql` | tool | cloud_engineer | Database selection/troubleshooting scenarios |
| `skill.cryptography` | Encryption & Key Management | `encryption`, `kms`, `tls`, `pki`, `key management`, `hashing` | concept | cloud_engineer, security_analyst | NEW·shared; secure-architecture domain both tracks |
| `skill.well-architected` | Well-Architected Framework | `well-architected`, `well-architected framework` | framework | cloud_engineer | SAA's four domains mirror its pillars |
| `skill.shared-responsibility` | Shared Responsibility Model | `shared responsibility`, `shared responsibility model` | concept | cloud_engineer | CLF-C02 anchor concept |
| `skill.storage-tiers` | Storage Tiers & Lifecycle | `storage classes`, `lifecycle policies`, `glacier`, `object vs block storage` | concept | cloud_engineer | Cost + performance design |
| `skill.cdn` | CDN & Edge | `cdn`, `cloudfront`, `content delivery network` | concept | cloud_engineer | Edge/performance design; secondary |
| `skill.cloud-migration` | Cloud Migration | `cloud migration`, `lift and shift`, `rehost`, `replatform` | concept | cloud_engineer | Enterprise posting language; secondary |
| `skill.cloud-cli` | Cloud CLIs | `aws cli`, `azure cli`, `az cli`, `gcloud`, `cloud shell` | tool | cloud_engineer | Daily driver; ACE tests gcloud explicitly |
| `skill.hybrid-connectivity` | Hybrid Connectivity | `site-to-site vpn`, `direct connect`, `expressroute` | concept | cloud_engineer | Hybrid architecture questions; secondary; bare `vpn` left out (generic) |
| `skill.landing-zones` | Landing Zones & Governance | `landing zone`, `control tower`, `azure policy`, `tagging strategy` | concept | cloud_engineer | Enterprise multi-account design; secondary |
| `skill.compliance` | Compliance Frameworks | `compliance`, `pci dss`, `hipaa`, `soc 2`, `fedramp`, `grc` | concept | cloud_engineer, security_analyst | NEW·shared; regulated-industry postings |
| `skill.cloud-resume-challenge` | Cloud Resume Challenge | `cloud resume challenge` | practice | cloud_engineer | The recognized cert-to-job bridge project |
| `skill.troubleshooting` | Systematic Troubleshooting | `troubleshooting`, `root cause analysis`? | practice | cloud_engineer | **Collision**: `root cause analysis`/`rca` proposed on `skill.postmortems` (devops) — one home; recommend leaving both aliases there and keeping only `troubleshooting` here |

**Optional / deferred:** Azure Bicep/ARM, AWS SAM, Fargate/ECS, GuardDuty
/Security Hub, cost-explorer tooling, multi-cloud as a concept.

## Alias-collision & FTS5 notes

- `aws lambda` → `skill.serverless` (existing); `route 53` →
  `skill.dns` (devops NEW·shared); `iam` etc. → `skill.iam`. Tag, don't
  mint.
- `rca`/`root cause analysis`: single home on `skill.postmortems`
  (recorded in `../02-shared-entries.md`).
- `compute`, `storage classes`, `encryption` are common-word-adjacent —
  expect optimistic FTS counts; interpret per-alias.
- `s3`, `ec2`, `vpc`, `kms` are short but distinctive tokens — good FTS
  signals, among the best in this track.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://docs.aws.amazon.com/aws-certification/latest/examguides/solutions-architect-associate-03.html | role_taxonomy | Official SAA-C03 guide w/ weights; stable until exam rev |
| https://d1.awsstatic.com/training-and-certification/docs-sa-assoc/AWS-Certified-Solutions-Architect-Associate_Exam-Guide_C03.pdf | role_taxonomy | PDF w/ in-scope service list — excellent extraction source |
| https://docs.aws.amazon.com/aws-certification/latest/examguides/cloud-practitioner-02.html | role_taxonomy | CLF-C02 entry-level scope |
| https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-104 | role_taxonomy | Revved in place with change log — re-ingest on update |
| https://services.google.com/fh/files/misc/associate_cloud_engineer_exam_guide_english.pdf | role_taxonomy | Official GCP ACE guide PDF |
| https://aws.amazon.com/architecture/well-architected/ | role_taxonomy | Six-pillar framework; stable, official |
| https://learn.microsoft.com/en-us/azure/architecture/ | role_taxonomy | Azure Architecture Center; official |
| https://cloudresumechallenge.dev/docs/the-challenge/ | role_taxonomy | Community-canonical prep project spec |
| https://prepfully.com/interview-guides/aws-cloud-support-engineer | interview_report | Loop-stage anatomy; commercial, moderately volatile |
| https://interviewkickstart.com/blogs/interview-questions/aws-cloud-support-engineer-interview-questions | interview_report | Scenario-question bank |
| https://aws.amazon.com/blogs/architecture/ | company_engineering_blog | Official reference architectures |
| https://cloud.google.com/blog/products/devops-sre | company_engineering_blog | GCP cloud-ops stream |
| (job boards: linkedin cloud-engineer searches) | official_job_posting | Highly volatile; sample per run |

## Enrichment expectations

`aws`, `terraform`, `iam`, `vpc`, `s3`, `ec2`, `kubernetes` should
dominate — the cert-guide corpus class practically guarantees it.
`cloud resume challenge` will only hit if its own site is ingested (it
is in the manifest for exactly that reason). `landing zone`/`control
tower` low counts are fine (enterprise-niche).

## Overlap with existing tracks

vs `devops_sre`: ~60% shared graph; distinctively cloud = provider-service
depth (storage tiers, database selection, hybrid connectivity, landing
zones, cost architecture) + cert-heavy hiring signal; distinctively devops
= pipeline construction, gitops, release engineering, SRE practices
("cloud engineers are essentially devops engineers who specialize in
cloud infrastructure products" — https://blog.boot.dev/devops/devops-vs-cloud-engineers/).
vs `swe`: moderate; coding rounds are lighter, service knowledge and
troubleshooting dominate.
