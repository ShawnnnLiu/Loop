# Network Engineer — Track Profile

**Proposed enum value:** `network_engineer` · **Wave 4** · Research grounded
2026-07-19.

## Track decision

Own track. Prep differs materially from every existing track: a canonical
three-rung cert ladder (CompTIA Network+ → CCNA 200-301 → CCNP Enterprise)
with published official blueprints, plus a hands-on CLI/lab culture
(Packet Tracer, GNS3, EVE-NG) that no other track shares. No DS&A, no
system-design-as-`swe`-knows-it; the interview loop is subnetting math +
scenario troubleshooting + live/virtual device configuration. Distinct
from `cloud_engineer` (provider-service depth, VPC-flavored networking)
and `devops_sre` (delivery pipelines) even where vocabulary touches —
this track owns the on-prem L2/L3 core those tracks only skim.

**Resolver markers:** `"network engineer"`, `"network administrator"`,
`"network admin"`, `"network technician"`, `"network analyst"`,
`"network operations"`, `"noc engineer"`, `"noc"`, `"ccna"`,
`"network architect"`, `"wireless engineer"`. Precedence hazards: insert
**after** `security_analyst` so "network security engineer" resolves via
its `"security engineer"` marker (that role preps like SA, not NE); keep
markers network-specific — `"sre"`/`"site reliability"` belong to
`devops_sre` and must not be shadowed. "cloud network engineer" contains
"network engineer" and will resolve here — acceptable (the prep is
NE-shaped with a cloud overlay), but flag for precedence review vs
`cloud_engineer` at implementation time. `noc` is a short marker but
boundary-matched against role strings, same class as devops' `sre`.

## Role snapshot

Designs, configures, and troubleshoots switched/routed networks — LANs,
WANs, wireless, firewalls, VPNs — on vendor gear (Cisco dominant), plus
increasing automation of that gear. BLS "network and computer systems
administrators": 331,500 jobs in 2024, median $96,800 (May 2024), ~14,300
openings/yr through 2034 despite a projected −4% employment change
(replacement-driven openings)
(https://www.bls.gov/ooh/computer-and-information-technology/network-and-computer-systems-administrators.htm).
The growth end of the same ladder, "computer network architects": 179,200
jobs, median $130,390, **+12%** (2024–34, much faster than average),
~11,200 openings/yr — driven by AI-infrastructure and cloud-transition
buildout
(https://www.bls.gov/ooh/computer-and-information-technology/computer-network-architects.htm).
The career story this track schedules: admin/NOC entry → CCNA-certified
engineer → CCNP/architect.

## Prep-process profile

- **Cert pipeline (the prep backbone; every rung has an official public
  blueprint — prime `role_taxonomy` corpus material):**
  - CompTIA Network+ N10-009, the vendor-neutral on-ramp: Networking
    Concepts 23%, Network Implementation 20%, Network Operations 19%,
    Network Security 14%, Network Troubleshooting 24%
    (https://www.comptia.org/en-us/certifications/network/).
  - Cisco CCNA 200-301 (v1.1, effective 2024-08-20), the hiring
    credential: Network Fundamentals 20%, Network Access 20%, IP
    Connectivity 25%, IP Services 10%, Security Fundamentals 15%,
    Automation & Programmability 10%
    (https://learningnetwork.cisco.com/s/ccna-exam-topics).
  - CCNP Enterprise core ENCOR 350-401: Architecture 15%, Virtualization
    10%, Infrastructure 30%, Network Assurance 10%, Security 20%,
    Automation 15% (https://learningnetwork.cisco.com/s/encor-exam-topics).
- **Interview loop:** recruiter screen → technical phone screen (OSI
  layers, TCP vs UDP, subnetting/CIDR arithmetic done live) →
  scenario-troubleshooting round ("user can't reach the server — walk me
  through it"; interviewers grade the *method*, ping/traceroute up the
  stack, not just the answer) → hands-on lab or config review (Packet
  Tracer/GNS3 or live gear: VLANs, OSPF adjacency, ACLs) → design +
  behavioral. Subnetting fluency is the canonical screen filter
  (https://www.networkbulls.com/blog/how-to-crack-a-network-engineer-interview-technical-practical-tips/,
  https://mindmajix.com/network-troubleshooting-interview-questions).
- **Anchor resources:** Jeremy's IT Lab free complete CCNA course, the
  community-default curriculum (https://www.jeremysitlab.com/); Professor
  Messer free N10-009 course
  (https://www.professormesser.com/network-plus/n10-009/n10-009-video/how-to-pass-your-n10-009-network-plus-exam/);
  Cisco Packet Tracer via NetAcad (https://www.netacad.com/cisco-packet-tracer);
  GNS3/EVE-NG for CCNP-level labs; Cloudflare Learning Center for
  protocol explainers (https://www.cloudflare.com/learning/).
- **Typical 12-week arc:** OSI/TCP-IP + IP addressing & subnetting drills
  → switching (VLANs/STP) + routing (OSPF) labs → services (NAT, DHCP,
  ACLs, wireless) + firewall/VPN basics → automation intro (Python/
  Ansible/REST) → daily subnetting reps + scenario-troubleshooting mocks
  + lab portfolio.

## Seed skill entries (draft)

### Existing entries — add `network_engineer` tag (~6)

`skill.networking` (owns `tcp/ip`, `computer networks` — the fundamentals
home; consider adding alias `osi model` in the next version),
`skill.load-balancing` (consider adding `f5`, `big-ip` — curation call),
`skill.linux`, `skill.python` (automation lingua franca), `skill.bash`,
`skill.git` (secondary — config/version hygiene).

Shared NEW entries defined in other profiles that also tag
`network_engineer`: `skill.dns` (devops-sre.md; owns `dns`, `route 53`),
`skill.ansible` (devops-sre.md; owns `configuration management` — network
automation's standard tool), `skill.troubleshooting` (cloud-engineer.md;
owns `troubleshooting`), `skill.wireshark` (security-analyst.md; owns
`wireshark`, `packet analysis`, `pcap` — reconciliation should mark it
NEW·shared SA+NE), `skill.high-availability` (devops-sre.md; secondary —
owns bare `redundancy`), `skill.hybrid-connectivity` (cloud-engineer.md;
secondary — owns `site-to-site vpn`, `direct connect`),
`skill.incident-response` (devops-sre.md; secondary — NOC shifts are
incident-driven).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.routing-protocols` | Routing Protocols | `routing protocols`, `ospf`, `bgp`, `eigrp`, `dynamic routing`, `static routing` | concept | network_engineer | 25% of CCNA (IP Connectivity) + core of ENCOR Infrastructure. Bare `routing` deliberately excluded (web-framework/message routing) |
| `skill.switching-vlans` | Switching & VLANs | `vlans`, `vlan`, `layer 2 switching`, `spanning tree`, `stp`, `trunking`, `etherchannel` | concept | network_engineer | 20% of CCNA (Network Access). Bare `switching` excluded (context switching etc.) |
| `skill.ip-addressing` | IP Addressing | `ip addressing`, `ipv4`, `ipv6`, `ipv6 addressing` | concept | network_engineer | The interview screen filter. `subnetting`/`cidr` CONTESTED — currently on `skill.cloud-networking` (cloud-engineer.md); see collision notes |
| `skill.cisco-ios` | Cisco IOS & NX-OS | `cisco ios`, `cisco`, `ios xe`, `nx-os` | tool | network_engineer | The dominant vendor CLI. Bare `ios` deliberately excluded (Apple iOS — mobile_engineer). `cisco` is vendor-broad; good FTS signal |
| `skill.firewalls` | Firewalls & ACLs | `firewalls`, `firewall`, `access control lists`, `acls`, `palo alto`, `fortinet`, `fortigate` | tool | network_engineer, security_analyst(2°) | NEW·shared candidate — security-analyst.md deferred exactly `palo alto`/`fortinet` to its optional line; one home, both tags |
| `skill.network-services` | IP Services (NAT/DHCP/NTP) | `nat`, `network address translation`, `dhcp`, `ntp` | concept | network_engineer | Mirrors CCNA domain 4.0 (10%). `nat` short — trust the long alias |
| `skill.wireless` | Wireless Networking | `wireless networking`, `wireless lan`, `wlan`, `wi-fi`, `wifi`, `802.11` | concept | network_engineer | CCNA Network Access + ENCOR Infrastructure; likely shared with it_support if that track lands |
| `skill.first-hop-redundancy` | First-Hop Redundancy | `hsrp`, `vrrp`, `first hop redundancy` | concept | network_engineer | CCNA IP Connectivity + ENCOR IP services; bare `redundancy` stays on `skill.high-availability` |
| `skill.network-monitoring` | Network Monitoring | `network monitoring`, `snmp`, `netflow`, `sflow`, `solarwinds` | tool | network_engineer | `monitoring`/`logging` stay on `skill.observability`; `syslog` stays on `skill.log-analysis` (SA) |
| `skill.network-automation` | Network Automation | `network automation`, `netmiko`, `napalm`, `netconf`, `restconf`, `pyats` | practice | network_engineer | 10% of CCNA, 15% of ENCOR; the career-growth differentiator. `napalm` collides with English — trust `netmiko`/`netconf` counts |
| `skill.sdn-sdwan` | SDN & SD-WAN | `sd-wan`, `sdwan`, `sdn`, `software-defined networking` | concept | network_engineer | ENCOR Architecture staple; rising posting keyword |
| `skill.qos` | Quality of Service | `qos`, `quality of service`, `traffic shaping` | concept | network_engineer | ENCOR Architecture; voice/video shops test it |
| `skill.network-access-control` | Network Access Control (AAA) | `802.1x`, `port security`, `radius`, `tacacs+` | concept | network_engineer | CCNA Security Fundamentals; `radius` collides with English prose — trust `tacacs+`/`802.1x`. Bare `aaa` excluded (noisy) |
| `skill.network-labs` | Network Labs & Simulators | `packet tracer`, `gns3`, `eve-ng`, `cisco modeling labs`, `home lab` | practice | network_engineer | THE no-experience hiring signal (parallel to SA's `skill.security-labs`); `home lab` possibly shared with it_support |

**Optional / deferred** (protect the ≤100 budget; add only if enrichment
or user demand supports them): MPLS, multicast, VoIP/collaboration
(`voip`, `sip`), Juniper Junos / Arista EOS as distinct vendor entries
(`junos`, `arista`), IPAM (`infoblox`), Meraki, Zabbix/Nagios/PRTG as
distinct monitoring entries, cabling/physical-layer (it_support
territory), Terraform-for-network (tag `skill.terraform` instead if
demand appears).

Running total: 14 new + 6 v1 tags + 7 shared tags ≈ **27 entries** —
comfortably under budget.

## Alias-collision & FTS5 notes

- `tcp/ip`, `networking`, `computer networks` → `skill.networking` (v1);
  `load balancing` → `skill.load-balancing` (v1); `dns`/`route 53` →
  `skill.dns` (devops); `troubleshooting` → `skill.troubleshooting`
  (cloud); `wireshark`/`packet analysis`/`pcap` → `skill.wireshark` (SA).
  Tag, don't mint.
- **CONTESTED — `subnetting`, `cidr`:** drafted on
  `skill.cloud-networking` (cloud-engineer.md) but they are the *defining*
  NE screen skill (CCNA IP addressing). Options for reconciliation: leave
  both on cloud's entry and have NE tag `skill.cloud-networking`, or move
  both to `skill.ip-addressing` and let cloud keep `vpc`/`security
  groups`/`vpc peering`. This profile does not claim them; `skill.ip-addressing`
  stands on `ip addressing`/`ipv4`/`ipv6` either way.
- **CONTESTED — `site-to-site vpn`:** on `skill.hybrid-connectivity`
  (cloud-engineer.md). NE tags that entry rather than fighting. Bare
  `vpn` is deliberately homeless (registry ruling) — no NE entry claims
  it; on-prem VPN skill resolves via `ipsec`-style long forms if a
  dedicated entry is ever wanted (deferred here to avoid a thin entry).
- `ids`/`snort`/`intrusion detection` → `skill.ids-ips` (SA);
  `tls`/`pki`/`encryption` → `skill.cryptography` (CE/SA);
  `configuration management` → `skill.ansible` (devops). Not claimed.
- Short/noisy FTS tokens in this track: `nat` (name "Nat"), `stp`,
  `sdn`, `qos`, `acls` (medical cert), `radius` (geometry), `napalm`
  (English), `cisco modeling labs`' abbreviation `cml` (excluded). Trust
  the long aliases (`network address translation`, `spanning tree`,
  `software-defined networking`, `quality of service`, `access control
  lists`). Résumé resolution is unaffected (surfaces arrive as skill
  mentions, not prose).
- `802.1x`, `802.11`, `tacacs+`, `sd-wan`: verify the FTS5 tokenizer's
  treatment of digits/dots/`+`/`-` before trusting counts — same class of
  problem as SA's `att&ck` note; the normalizer preserves them, index
  tokenization is a separate question.
- Suggested alias additions to existing entries (curation review, next
  version): `skill.networking` += `osi model`; `skill.troubleshooting` +=
  `network troubleshooting`; `skill.load-balancing` += `f5`, `big-ip`.
- it_support (drafted in parallel): recommend it tag `skill.networking`,
  `skill.wireless`, `skill.network-services`, and `skill.network-labs`
  (`home lab`) rather than minting a separate networking-fundamentals
  entry — the v1 `skill.networking` entry *is* the shared fundamentals
  home. If it_support insists on its own entry, that is a CONTESTED call
  for reconciliation.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://learningnetwork.cisco.com/s/ccna-exam-topics | role_taxonomy | Official CCNA 200-301 v1.1 blueprint w/ weights; revs on exam version (~3–5 yr) |
| https://learningnetwork.cisco.com/s/encor-exam-topics | role_taxonomy | Official ENCOR 350-401 blueprint w/ weights; v1.2 rev cadence |
| https://www.comptia.org/en-us/certifications/network/ | role_taxonomy | N10-009 canonical page (objectives PDF lives on a CDN that may rot — same pattern as Security+) |
| https://www.jeremysitlab.com/ | role_taxonomy | Community-default free CCNA curriculum; stable |
| https://www.professormesser.com/network-plus/n10-009/n10-009-video/how-to-pass-your-n10-009-network-plus-exam/ | role_taxonomy | Free N10-009 course hub; URL churns per exam version |
| https://www.cloudflare.com/learning/ | role_taxonomy | High-quality protocol explainers (BGP, DNS, OSI); stable, free |
| https://packetlife.net/library/cheat-sheets/ | role_taxonomy | Canonical protocol cheat sheets; stable for a decade+ |
| https://www.netacad.com/cisco-packet-tracer | role_taxonomy | Official Packet Tracer home; lab-prep anchor |
| https://www.bls.gov/ooh/computer-and-information-technology/network-and-computer-systems-administrators.htm | role_taxonomy | BLS OOH figures; annual rev; **served 403 to generic fetchers in testing — ingestion may need UA handling** |
| https://ipcisco.com/network-engineer-interview-questions-and-answers/ | interview_report | 300+ question bank by topic; commercial, moderately volatile |
| https://www.networkbulls.com/blog/how-to-crack-a-network-engineer-interview-technical-practical-tips/ | interview_report | Loop-stage anatomy incl. practical test |
| https://mindmajix.com/network-troubleshooting-interview-questions | interview_report | Troubleshooting-methodology bank; refreshed yearly |
| https://github.com/networktocode/awesome-network-automation | role_taxonomy | Curated automation-tooling map; check repo license before snapshot |
| https://blog.networktocode.com/ | company_engineering_blog | Network-automation practice stream |
| (job boards: linkedin/indeed network-engineer searches) | official_job_posting | Highly volatile (45-day prior); sample per run |

## Enrichment expectations

`cisco`, `ospf`, `bgp`, `vlan`, `firewall`, `dns`, `wireshark`, `snmp`
should dominate — the cert-blueprint corpus class guarantees it. Expect
unreliable raw counts for `nat`, `radius`, `napalm`, `stp` (English/
abbreviation collisions — read per-alias, trust long forms). Zero/low
support is fine to keep for `eve-ng`, `pyats`, `tacacs+`, `cisco modeling
labs` (niche but real résumé surfaces). If `subnetting`-adjacent terms
come back zero under `skill.ip-addressing`, that is the contested-alias
ruling showing up in the data, not a missing document class.

## Overlap with existing tracks

vs `cloud_engineer`: the real boundary dispute — both need IP networking;
CE's home is provider constructs (VPC, security groups), NE's is on-prem
L2/L3 + vendor gear; shared: `skill.networking`, `skill.dns`,
`skill.load-balancing`, `skill.hybrid-connectivity`, contested
`subnetting`/`cidr`. vs `devops_sre`: shares Linux/automation/monitoring
posture, none of the L2/switching/wireless core; `skill.ansible` is the
bridge. vs `security_analyst`: shares packet analysis and the firewall
surface (one shared `skill.firewalls` entry, different prep emphasis).
vs `swe`: nearly disjoint (no DS&A, no application coding beyond
automation Python). vs it_support (parallel draft): NE is the
depth-progression of ITS's networking slice — share fundamentals entries
via tags, not duplicates.
