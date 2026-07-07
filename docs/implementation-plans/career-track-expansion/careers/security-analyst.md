# Cybersecurity Analyst (SOC) — Track Profile

**Proposed enum value:** `security_analyst` · **Wave 1** · Research
grounded 2026-07-06.

## Track decision

Own track, fully separate — distinct cert spine (Security+ → CySA+ →
CISSP), distinct tooling (SIEM/EDR), and a distinct interview format
(scenario/log-analysis rounds, **no algorithmic coding**). The
security-*engineer* variant (designs/builds controls, higher pay) is
modeled as this track's growth branch, not a separate track: postings
share one on-ramp, and the bridge skills (detection tuning, scripting,
SOAR) are in this vocabulary.

**Resolver markers:** `"security analyst"`, `"soc analyst"`,
`"cybersecurity"`, `"cyber security"`, `"information security"`,
`"infosec"`, `"security engineer"`, `"security operations"`,
`"incident responder"`, `"threat analyst"`.

## Role snapshot

Monitors networks/systems via SIEM/EDR, triages alerts, investigates
incidents, reports on threats. Demand evidence is exceptional: BLS
projects **29% growth 2024–2034** (~16k openings/yr —
https://www.bls.gov/ooh/computer-and-information-technology/information-security-analysts.htm);
CyberSeek counted ~514k US cybersecurity postings May 2024–Apr 2025 with
only 74 workers per 100 openings (https://www.cyberseek.org/heatmap.html).
The most certification-codified prep path of any tech career researched.

## Prep-process profile

- **Anchor certifications** (official syllabi with published domain
  weights — prime corpus material):
  - CompTIA Security+ (SY0-701), the entry anchor (70k+ postings request
    it; DoD baseline): Security Operations 28%, Threats/Vulns 22%,
    Program Mgmt 20%, Architecture 18%, General Concepts 12%.
  - CompTIA CySA+ (CS0-003), the analyst-role anchor: SecOps 33%, Vuln
    Mgmt 30%, Incident Response 20%, Reporting 17%. (CS0-004 succession
    underway — re-check at ingestion.)
  - ISC2 CC (free on-ramp), CompTIA Network+ (common precursor),
    Microsoft SC-200 (Microsoft-stack SOC: manage secops environment
    40–45%, respond 35–40%, hunt 20–25%), CISSP as the seniority filter
    (https://www.cyberseek.org/certifications.html).
- **Interview loop:** recruiter → technical round with scenarios or live
  log analysis (phishing-alert walkthrough, suspicious outbound traffic,
  brute-force triage; often hands-on SIEM) → hiring-manager round
  (incident narratives, escalation judgment). Expected answer skeleton:
  identify alert → gather context/logs → benign-vs-suspicious verdict →
  escalate → document
  (https://www.infosectrain.com/blog/20-most-common-soc-analyst-interview-questions-and-answers).
- **Typical 12-week arc:** networking foundations (Network+-level) →
  Security+ domains → hands-on SOC labs (TryHackMe SOC Level 1 /
  LetsDefend simulated SOC) → MITRE ATT&CK fluency + Splunk/Sentinel query
  practice + scenario mocks (https://tryhackme.com/path/outline/soclevel1).

## Seed skill entries (draft)

### Existing entries — add `security_analyst` tag (~8)

`skill.python`, `skill.bash`, `skill.sql` (secondary), `skill.linux`,
`skill.networking` (owns `tcp/ip`), `skill.git` (secondary),
`skill.authentication` (owns `oauth`, `authorization` — identity attacks
dominate incidents), `skill.application-security` (owns the bare
`security` alias — note below).

### New entries

Shared NEW entries defined elsewhere that tag `security_analyst`:
`skill.iam`, `skill.incident-response`, `skill.powershell`,
`skill.cryptography`, `skill.compliance`, `skill.devsecops`,
`skill.secrets-management` (secondary), `skill.postmortems` (secondary).

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.siem` | SIEM Operations | `siem`, `security information and event management`, `log correlation` | concept | security_analyst | The role's central system |
| `skill.splunk` | Splunk | `splunk`, `spl`, `splunk enterprise security` | tool | security_analyst | Most-named SIEM in postings |
| `skill.sentinel` | Microsoft Sentinel | `microsoft sentinel`, `sentinel`, `kql`, `kusto` | tool | security_analyst | SC-200 anchor; folding the KQL language in is a curation call |
| `skill.edr` | EDR Platforms | `edr`, `endpoint detection and response`, `crowdstrike`, `defender for endpoint`, `sentinelone` | tool | security_analyst | Endpoint telemetry = half of modern triage; product bundling is a curation call |
| `skill.mitre-attack` | MITRE ATT&CK | `mitre att&ck`, `mitre attack`, `att&ck`, `ttps` | framework | security_analyst | Universal detection/hunting vocabulary |
| `skill.security-frameworks` | Security Frameworks | `nist csf`, `nist 800-61`, `cyber kill chain`, `kill chain`, `iso 27001` | framework | security_analyst | Scenario-answer skeletons; bundling is a curation call |
| `skill.owasp` | OWASP Top 10 | `owasp`, `owasp top 10` | framework | security_analyst | Web-attack literacy; arguably also `swe` — curation call |
| `skill.threat-hunting` | Threat Hunting | `threat hunting`, `hunting hypotheses` | concept | security_analyst | 20–25% of SC-200; tier-2 differentiator |
| `skill.threat-intelligence` | Threat Intelligence | `threat intelligence`, `cti`, `iocs`, `indicators of compromise` | concept | security_analyst | Enrichment + campaign awareness |
| `skill.vulnerability-management` | Vulnerability Management | `vulnerability management`, `vulnerability scanning`, `cve`, `cvss`, `nessus`, `qualys` | concept | security_analyst | 30% of CySA+; scanner products folded in (curation call) |
| `skill.phishing-analysis` | Phishing Analysis | `phishing analysis`, `email security`, `email headers`, `bec` | concept | security_analyst | Highest-volume alert category |
| `skill.malware-analysis` | Malware Analysis | `malware analysis`, `sandbox analysis`, `ransomware analysis` | concept | security_analyst | Triage-level literacy; bare `ransomware` too generic for one skill |
| `skill.log-analysis` | Log Analysis | `log analysis`, `windows event logs`, `syslog`, `sysmon` | practice | security_analyst | Core daily work; distinct from `skill.observability` (`logging` stays there) |
| `skill.wireshark` | Wireshark & Packet Analysis | `wireshark`, `packet analysis`, `pcap` | tool | security_analyst | Network forensics staple |
| `skill.nmap` | Nmap | `nmap`, `port scanning` | tool | security_analyst | Recon literacy both directions |
| `skill.ids-ips` | IDS/IPS | `ids`, `ips`, `intrusion detection`, `snort`, `suricata`, `zeek` | tool | security_analyst | Network detection layer |
| `skill.soar` | SOAR & Security Automation | `soar`, `security orchestration`, `security automation` | tool | security_analyst | Playbook automation; analyst→engineer bridge |
| `skill.active-directory` | Active Directory & Entra ID | `active directory`, `entra id`, `azure ad`, `ldap`, `kerberos` | tool | security_analyst, cloud_engineer | NEW·shared; identity attacks dominate incidents |
| `skill.attack-techniques` | Attack Techniques | `lateral movement`, `privilege escalation`, `persistence techniques` | concept | security_analyst | ATT&CK tactic fluency; bare `persistence` too generic |
| `skill.zero-trust` | Zero Trust | `zero trust`, `zta`, `microsegmentation` | concept | security_analyst | Architecture posting keyword; secondary |
| `skill.cloud-security` | Cloud Security | `cloud security`, `cspm`, `cloudtrail` | concept | security_analyst, cloud_engineer | NEW·shared; cloud log sources now standard in SOCs |
| `skill.alert-triage` | Alert Triage | `alert triage`, `triage`, `alert investigation` | practice | security_analyst | The tier-1 job description |
| `skill.detection-engineering` | Detection Engineering | `detection engineering`, `detection rules`, `sigma rules`, `alert tuning`, `false positive reduction` | practice | security_analyst | Analyst→engineer growth path; owns `alert tuning` taxonomy-wide |
| `skill.threat-reporting` | Investigation Reporting | `incident reports`, `report writing`, `chain of custody` | practice | security_analyst | 17% of CySA+; evidence handling folded in |
| `skill.security-labs` | Security Labs & CTFs | `tryhackme`, `hack the box`, `htb`, `letsdefend`, `capture the flag`, `ctf` | practice | security_analyst | THE hiring signal for no-experience candidates |
| `skill.virustotal` | Reputation & Sandboxing | `virustotal`, `hybrid analysis` | tool | security_analyst | File/url triage; secondary |
| `skill.digital-forensics` | Digital Forensics | `digital forensics`, `disk forensics`, `autopsy` | practice | security_analyst | Tier-2/3; secondary |

**Optional / deferred:** MISP/threat-intel platforms, firewalls/WAF
(`palo alto`, `fortinet`), Burp Suite, DLP, QRadar/Elastic-Security as
distinct SIEM entries, regex (generic), ticketing (`servicenow` — generic
IT).

## Alias-collision & FTS5 notes

- The bare `security` alias already lives on `skill.application-security`
  (v1, swe) — the security track tags that entry rather than fighting for
  the token. Same for `logging`/`monitoring` (`skill.observability`).
- `triage`, `hunting`, `persistence`, `ransomware` are common-English
  tokens — the multi-word aliases are the trustworthy FTS signals. `ids`
  collides with the plural of "id" in prose; expect noise; trust
  `intrusion detection`.
- `kerberos` placed on `skill.active-directory`, not on
  `skill.authentication` (which keeps oauth/oauth2) — one home each.
- `att&ck`: verify the FTS5 tokenizer's treatment of `&` before relying
  on its counts (same class of problem as `c++`/`c#` — the normalizer
  preserves it, but the *index* tokenization is a separate question worth
  one test in RI-F).

## Candidate corpus sources (manifest seeds)

The best-licensed track of all: NIST/CISA material is US-gov public
domain.

| URL | expected type | note |
|---|---|---|
| https://csrc.nist.gov/pubs/sp/800/181/r1/final | role_taxonomy | NICE Framework — THE authoritative skill/KSA taxonomy; public domain |
| https://niccs.cisa.gov/tools/nice-framework/work-role/defensive-cybersecurity | role_taxonomy | NICE "Defensive Cybersecurity" work role w/ tasks/KSAs; official |
| https://www.comptia.org/en-us/certifications/security/ | role_taxonomy | SY0-701 canonical page (objectives PDF lives on a CDN that may rot) |
| https://www.isc2.org/certifications/cc/cc-certification-exam-outline | role_taxonomy | Official ISC2 CC outline w/ weights |
| https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/sc-200 | role_taxonomy | SC-200 study guide; revved in place — re-ingest quarterly |
| https://attack.mitre.org/ | role_taxonomy | ATT&CK knowledge base; free w/ attribution; versioned releases |
| https://csrc.nist.gov/pubs/sp/800/61/r2/final | role_taxonomy | Incident-handling guide (check r3 supersession); public domain |
| https://roadmap.sh/cyber-security | role_taxonomy | Community roadmap; stable |
| https://www.cyberseek.org/ | role_taxonomy | NIST-funded supply/demand + cert-demand data; ~annual updates |
| https://www.bls.gov/ooh/computer-and-information-technology/information-security-analysts.htm | role_taxonomy | Official outlook; public domain |
| https://www.infosectrain.com/blog/20-most-common-soc-analyst-interview-questions-and-answers | interview_report | Representative question set; commercial blog |
| https://cyberdefenders.org/blog/start-your-career-as-a-soc-analyst/ | interview_report | Practitioner-written path incl. hiring expectations |
| https://thedfirreport.com/ | company_engineering_blog | Real intrusion breakdowns — closest to public SOC postmortems |
| https://redcanary.com/blog/ | company_engineering_blog | Detection-engineering content; vendor blog, stable |

## Enrichment expectations

`siem`, `incident response`, `splunk`, `mitre att&ck` (tokenizer caveat),
`vulnerability management`, `phishing` should dominate given the
cert-syllabus + NICE corpus class. `sigma rules`, `zeek`, `autopsy`
likely low — fine. If `threat hunting` flags zero, ingest an SC-200 or
TryHackMe path page.

## Overlap with existing tracks

The smallest overlap with existing tracks of any wave-1 career (~8
existing entries): linux, networking, python/bash, git. This is the
expensive one to add — most entries are new, and the weak-spot prompt
slice will be almost entirely fresh vocabulary. Budget accordingly (~45
entries; well under the ~100 cap). Overlaps `cloud_engineer` on
iam/cryptography/compliance/cloud-security/active-directory.
