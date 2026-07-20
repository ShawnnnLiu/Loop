# IT Support / Help Desk Specialist — Track Profile

**Proposed enum value:** `it_support` · **Wave 4** · Research grounded
2026-07-19.

## Track decision

Own track — the most cert-codified entry path in tech and the only one
here with **no coding round at all**. Prep is anchored on two codified
credentials (CompTIA A+ Core 1+2, Google IT Support Certificate) plus
ITIL vocabulary, and the interview is scenario walkthroughs + customer
service, not DS&A or system design — materially different from every
existing track per the granularity policy. Tier 1/2/3 stay one track
(tier is seniority, not a different prep process). This is also the
classic feeder into `security_analyst`, `devops_sre`, and the
`network_engineer` track being drafted in parallel — the profile leans on
shared entries at those boundaries rather than duplicating them.

**Resolver markers:** `"help desk"`, `"helpdesk"`, `"it support"`,
`"desktop support"`, `"service desk"`, `"technical support"`,
`"it technician"`, `"support technician"`, `"support specialist"`,
`"it specialist"`. Precedence notes: `"technical support engineer"`
must resolve here, not fall through to `swe` on "engineer"-adjacent
matching; `"support specialist"`/`"it specialist"` are generous
catch-alls — insert after more specific tracks (a "product support
engineer" or "customer support engineer" title still belongs here, but
`"application support engineer"` is a judgment call vs `swe`). No
collisions with existing marker sets (checked against swe, devops_sre,
cloud_engineer, security_analyst).

## Role snapshot

First line of IT: triages user tickets, troubleshoots hardware/OS/
network/application issues, administers accounts and devices, escalates
per SLA. BLS (computer support specialists): median **$60,340** (May
2024) and about **50,500 openings/yr** projected over the decade — but
employment is projected to **decline 3% 2024–34**, with essentially all
openings from replacement
(https://www.bls.gov/ooh/computer-and-information-technology/computer-support-specialists.htm).
Honest positioning: enormous absolute volume and the lowest barrier to
entry in tech, but not a growth occupation — the prep story is
"on-ramp + escalation path", which is exactly what a study plan can
schedule. Posting analyses consistently rank ticketing systems
(ServiceNow/Jira), Windows/Mac troubleshooting, Active Directory, and
Microsoft 365 as the top requested skills
(https://www.resumeadapter.com/blog/help-desk-resume-keywords).

## Prep-process profile

- **Anchor certifications** (official blueprints with published weights —
  prime `role_taxonomy` corpus material):
  - CompTIA A+ **Core 1 (220-1201)**, V15 launched 2025-03-25: Mobile
    Devices 13%, Networking 23%, Hardware 25%, Virtualization & Cloud
    Computing 11%, Hardware & Network Troubleshooting 28%
    (https://www.comptia.org/en-us/certifications/a/core-1-and-2-v15/).
  - CompTIA A+ **Core 2 (220-1202)**: Operating Systems 28%, Security
    28%, Software Troubleshooting 23%, Operational Procedures 21%
    (https://crucialexams.com/exams/comptia/a/220-1202/p/comptia-a-220-1202-v15-exam-objectives).
  - Google IT Support Professional Certificate (~5 courses/~26 weeks:
    technical support fundamentals, networking, operating systems,
    system administration, security; explicitly aligned to A+ —
    https://www.coursera.org/professional-certificates/google-it-support).
  - ITIL 4 Foundation (PeopleCert; 40 questions/60 min; service value
    system, incident/problem/change/service-desk practices —
    https://www.peoplecert.org/browse-certifications/it-governance-and-service-management/ITIL-1/itil-4-foundation-2565).
  - Growth-path certs one rung up: CompTIA Network+ (→ network_engineer),
    Microsoft MD-102 Endpoint Administrator (Intune/MDM shops),
    Security+ (→ security_analyst).
- **Interview loop:** recruiter screen → technical/scenario round
  ("computer won't connect to the network — walk me through it": check
  physical layer → ipconfig → ping gateway → DNS → escalate) →
  behavioral/customer-service round (angry-user handling, ticket
  prioritization by impact/urgency and SLA) → sometimes a live mock
  ticket or hiring-manager round
  (https://www.indeed.com/career-advice/interviewing/help-desk-interview-questions,
  https://ccitraining.edu/blog/common-it-support-interview-questions/).
  The named failure mode: reciting facts instead of demonstrating a
  repeatable troubleshooting method plus calm user communication.
- **Typical 12-week arc:** hardware + OS fundamentals with a home lab
  (Core 1 domains) → networking basics (tcp/ip, dns, dhcp at
  Network+-lite depth) → Core 2 OS/security + Active Directory and
  ticketing-workflow labs → ITIL vocabulary + scenario mocks +
  customer-service drills + A+ exam sits.

## Seed skill entries (draft)

### Existing entries — add `it_support` tag (~13)

From v1: `skill.linux`, `skill.networking` (owns `tcp/ip`, `computer
networks` — Core 1's 23% domain; alias additions proposed below),
`skill.operating-systems` (owns `operating systems` — Core 2's 28%
domain), `skill.bash` (secondary; owns `shell`), `skill.authentication`
(secondary; owns `oauth` — consider adding `mfa`, `multi-factor
authentication` in the next version), `skill.python` (secondary; the
Google IT Automation follow-on cert).

In-flight NEW entries from other profiles that add `it_support`:
`skill.troubleshooting` (cloud-engineer.md — owns `troubleshooting`; the
single most-requested help-desk skill, do not re-mint),
`skill.active-directory` (security-analyst.md — owns `active directory`,
`azure ad`, `entra id`, `kerberos`; password resets/joins are daily tier-1
work), `skill.powershell` (devops-sre.md), `skill.jira`
(product-manager.md — owns `jira`, `atlassian jira`),
`skill.incident-response` (devops-sre.md — owns `incident management`,
the ITIL practice name; tag rather than fight for the alias), `skill.dns`
(secondary; devops-sre.md), `skill.iam` (secondary; devops-sre.md — owns
`rbac`, `least privilege`).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.windows` | Windows Administration | `windows`, `microsoft windows`, `windows 10`, `windows 11`, `windows server` | tool | it_support | Backbone of the role; `windows event logs` stays on SA `skill.log-analysis`. `windows server` is CONTESTED (network_engineer may want a dedicated entry) |
| `skill.macos` | macOS Support | `macos`, `mac os`, `os x` | tool | it_support | Mac fleets standard in postings; `jamf` lives on `skill.mdm` below |
| `skill.hardware-support` | PC Hardware & Peripherals | `computer hardware`, `pc hardware`, `hardware troubleshooting`, `pc assembly`, `printers`, `printer troubleshooting`, `peripherals` | concept | it_support | 25% of Core 1; bare `hardware` too generic — deliberately not an alias |
| `skill.ticketing-systems` | Ticketing Systems | `ticketing systems`, `ticketing`, `servicenow`, `zendesk`, `freshservice`, `freshdesk`, `jira service management` | tool | it_support | Product bundling is a curation call (SA `skill.edr` precedent); security-analyst.md explicitly deferred `servicenow` as "generic IT" — it lands here |
| `skill.itil` | ITIL & IT Service Management | `itil`, `itil 4`, `itsm`, `it service management`, `problem management`, `change enablement`, `sla`, `service level agreement` | framework | it_support | `incident management` deliberately NOT here (owned by `skill.incident-response`); `change management` ruled 2026-07-19 to `skill.change-management` (management-consultant.md, MC+HR) — ITIL keeps ITIL 4's own term `change enablement`; `sla` noisy — see below |
| `skill.microsoft-365` | Microsoft 365 Administration | `microsoft 365`, `m365`, `office 365`, `o365`, `microsoft office`, `exchange online`, `sharepoint`, `microsoft teams`, `outlook` | tool | it_support | Top-3 posting skill; bare `teams` deliberately not an alias (common English); `outlook` FTS-noisy — see notes |
| `skill.google-workspace` | Google Workspace Admin | `google workspace`, `g suite`, `gsuite` | tool | it_support | The non-Microsoft half of SMB support |
| `skill.remote-support` | Remote Support Tools | `remote support`, `remote desktop`, `rdp`, `remote assistance`, `teamviewer`, `anydesk`, `vnc` | tool | it_support | Post-2020 table stakes; bare `vpn` stays deliberately homeless — remote-access support is covered here without it |
| `skill.mdm` | Endpoint & Mobile Device Management | `mdm`, `mobile device management`, `endpoint management`, `intune`, `microsoft intune`, `jamf`, `sccm`, `microsoft endpoint configuration manager` | tool | it_support | MD-102 anchor; covers Core 1's mobile-devices domain from the admin side. Adjacent to SA `skill.edr` (which keeps `defender for endpoint`) |
| `skill.os-deployment` | OS Deployment & Imaging | `os deployment`, `os imaging`, `system imaging`, `disk imaging`, `windows deployment` | practice | it_support | Fleet provisioning; bare `imaging` too generic — not an alias |
| `skill.account-administration` | User Account Administration | `user account management`, `account provisioning`, `password resets`, `password reset`, `user onboarding` | practice | it_support | The daily posting language; the AD/IAM entries hold the tools/concepts, this holds the task |
| `skill.endpoint-protection` | Endpoint Protection Basics | `antivirus`, `anti-virus`, `endpoint protection`, `malware removal`, `windows defender` | concept | it_support | Tier-1 security surface (Core 2 Security 28%); `windows defender` CONTESTED-adjacent with SA `skill.edr` — see notes |
| `skill.virtualization` | Virtualization Basics | `virtualization`, `vmware`, `hyper-v`, `virtual machines`, `virtual machine` | concept | it_support | 11% of Core 1; unclaimed by cloud_engineer — they may want a tag (curation call) |
| `skill.customer-service` | Customer Service & Communication | `customer service`, `customer support`, `phone support`, `de-escalation` | practice | it_support | The interview differentiator; distinct from `skill.stakeholder-communication` (DA/PM) |
| `skill.knowledge-base` | Knowledge Base & Documentation Practice | `knowledge base`, `kb articles`, `knowledge management` | practice | it_support | Ticket-hygiene signal; bare `documentation` stays deliberately homeless |

**Optional / deferred** (protect the budget; add only on enrichment or
user demand): iOS/Android end-user support as a distinct entry, Citrix/
VDI, telephony/VoIP (`voip`), asset management/CMDB, `skill.disaster-recovery`
tag for backup literacy (`backup and restore` already lives there),
chrome os / chromebook fleet support, Okta/SSO administration (`sso`,
`single sign-on` — unclaimed today; likely better minted by a future
identity-flavored entry).

Total ≈ 13 existing-tagged + 15 new ≈ **28 entries** — well under the
~55 self-cap and the ~100 prompt budget.

## Alias-collision & FTS5 notes

- `troubleshooting` → already minted on cloud-engineer.md's
  `skill.troubleshooting`; `incident management` → on
  `skill.incident-response` (devops-sre.md); `active directory`/`azure
  ad`/`kerberos` → on `skill.active-directory` (security-analyst.md);
  `jira` → on `skill.jira` (product-manager.md). Tag, never re-mint.
- **Networking fundamentals:** v1 `skill.networking` owns `networking`,
  `tcp/ip`, `computer networks` — this track tags it rather than minting
  a `networking-fundamentals` entry. Ruled 2026-07-19: `dhcp` lives on
  network-engineer.md's `skill.network-services` and `subnetting`/`cidr`
  stay on cloud-engineer.md's `skill.cloud-networking` — it_support tags
  those entries instead. Surviving alias proposals for v1
  `skill.networking`'s next version: `network troubleshooting`,
  `osi model`, `network fundamentals` (network_engineer's profile
  independently proposes `osi model` too — compatible).
- `jira service management` placed on `skill.ticketing-systems` while
  bare `jira` stays on `skill.jira` (PM) — globally unique either way;
  splitting the product family across two entries is a deliberate
  curation call worth a reconciliation look.
- Short/noisy FTS tokens: `mdm`, `rdp`, `o365`, `sla`, `itil` are short
  but distinctive in tech prose; `outlook` collides badly with ordinary
  English (BLS pages literally say "job outlook") — keep it for résumé
  resolution but treat its corpus counts as unusable and trust
  `office 365`/`exchange online`; `ticketing` and `windows` are
  common-ish words — trust `ticketing systems` and the versioned
  `windows 10`/`windows 11` counts.
- Deliberately not claimed: bare `hardware`, `imaging`, `teams`, `vpn`,
  `documentation`, `sso` (deferred), `it` — generic or homeless per
  `../02-shared-entries.md`.
- Proposed additions to existing v1 entries (curation review, next
  version): `skill.authentication` += `mfa`, `multi-factor
  authentication`; `skill.networking` += the contested list above.

## Candidate corpus sources (manifest seeds)

Blueprint-anchored; never ingest commercial prep-course material
(Messer/Meyers/Dion class) — official pages and free explainers only.

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/computer-and-information-technology/computer-support-specialists.htm | role_taxonomy | Official outlook + duties; public domain; annual refresh |
| https://www.comptia.org/en-us/certifications/a/core-1-and-2-v15/ | role_taxonomy | Canonical A+ V15 page (220-1201/1202); objectives PDFs live on a CDN that may rot |
| https://www.comptia.org/en/certifications/a/core-1-v15/ | role_taxonomy | Core 1 domain detail; comptia.org URL structure churns — re-verify at ingestion |
| https://crucialexams.com/exams/comptia/a/220-1202/p/comptia-a-220-1202-v15-exam-objectives | role_taxonomy | Free Core 2 objectives mirror w/ weights; use official PDF if resolvable |
| https://www.coursera.org/professional-certificates/google-it-support | role_taxonomy | Google IT Support cert syllabus; marketing page, occasionally restructured |
| https://www.coursera.org/learn/technical-support-fundamentals | role_taxonomy | Course-1 syllabus detail; stable for years |
| https://grow.google/certificates/it-support/ | role_taxonomy | Google's own program page w/ role framing |
| https://www.peoplecert.org/browse-certifications/it-governance-and-service-management/ITIL-1/itil-4-foundation-2565 | role_taxonomy | Official ITIL 4 Foundation outline; ITIL text itself is copyrighted — page only |
| https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/md-102 | role_taxonomy | Official MD-102 study guide (Intune/MDM vocabulary); revved in place — re-ingest quarterly |
| https://www.comptia.org/en-us/certifications/network/ | role_taxonomy | Network+ (the growth-path cert); shared interest with network_engineer track |
| https://www.atlassian.com/itsm | role_taxonomy | Free ITSM/service-desk practice explainers; vendor guide, stable |
| https://www.indeed.com/career-advice/interviewing/help-desk-interview-questions | interview_report | 39 questions + samples; refreshed yearly |
| https://ccitraining.edu/blog/common-it-support-interview-questions/ | interview_report | Scenario-heavy question set incl. troubleshooting method |
| https://www.novelvista.com/blogs/interview-questions/for-it-help-desk-with-answers | interview_report | 100+ questions; commercial blog, volatile |
| (job boards: linkedin/indeed help-desk / desktop-support searches) | official_job_posting | Volatile (45-day prior) + ToS limits; sample per run |

## Enrichment expectations

`windows`, `active directory`, `troubleshooting`, `ticketing systems`,
`servicenow`, `microsoft 365`/`office 365`, `customer service` should
dominate given the blueprint + posting corpus. Treat `outlook` and bare
`ticketing`/`windows` counts as advisory only (noise notes above).
Likely zero/low-support but keep: `g suite`, `anydesk`, `disk imaging`,
`kb articles` — résumé-resolution value stands on its own. If `itil` or
`mdm` flag zero, the manifest is missing the PeopleCert/MD-102 pages —
fix the manifest, not the entries.

## Overlap with existing tracks

The feeder track: overlaps `security_analyst` on
active-directory/networking/linux/powershell (and Security+ is the named
next rung), `devops_sre`/`cloud_engineer` on
powershell/dns/iam/incident-response, and the parallel `network_engineer`
draft on everything networking-flavored — that boundary is the main
reconciliation surface (see CONTESTED list). Near-zero overlap with the
data and design tracks. ~13 of ~28 entries are shared, so the track is
mid-cost to add; its distinctive vocabulary (ticketing, ITSM, endpoint
management, customer service) exists nowhere else in the taxonomy.
