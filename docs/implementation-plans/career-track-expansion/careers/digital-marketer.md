# Digital Marketing Specialist — Track Profile

**Proposed enum value:** `digital_marketer` · **Wave 4** · Research grounded
2026-07-19.

## Track decision

Own track — prep process is materially different from every existing
track: no coding loop, a codified certificate stack (Google Digital
Marketing & E-commerce Certificate, Google Ads certifications on
Skillshop, GA4, HubSpot Academy, Meta Blueprint), and a
portfolio-plus-mock-campaign interview loop. 78% of marketing hiring
managers expect portfolio work in the interview and 63% won't advance
candidates who can't show strategic thinking through real examples
(https://jobprepped.com/digital-marketing-portfolio-guide/). Skill set is
near-disjoint from all nine existing tracks; the only real adjacency is
the analytics slice shared with `data_analyst`/`product_manager`.

Granularity call: SEO specialist, PPC/paid-media specialist, content
marketer, social media manager, and email marketer are **specializations
inside this one track**, not separate tracks — same cert anchors, same
loop shape (screen → portfolio walkthrough → channel deep-dive → mock
campaign), overlapping core vocabulary. Splitting them would produce
five thin tracks and dilute the unresolved-role union fallback.

**Resolver markers:** `"digital marketing"`, `"digital marketer"`,
`"marketing specialist"`, `"marketing coordinator"`,
`"marketing manager"`, `"marketing analytics"`, `"performance marketing"`,
`"growth marketing"`, `"paid media"`, `"paid search"`, `"media buyer"`,
`"ppc"`, `"seo"`, `"sem specialist"`, `"content marketing"`,
`"content marketer"`, `"social media marketing"`,
`"social media manager"`, `"email marketing"`, `"ecommerce marketing"`,
`"e-commerce marketing"`, `"demand generation"`, `"brand marketing"`.

Precedence hazards:

- Must be inserted **before** `data_analyst`: DA's bare `"analytics"`
  marker would otherwise swallow "marketing analytics manager". Bare
  `"marketing analyst"` is a judgment call (many are DA-shaped roles that
  happen to sit in marketing) — flag for precedence review at
  implementation, same status as DA's "product analyst".
- Must be checked against `product_manager`: "product marketing manager"
  contains "marketing manager" (resolves here, defensible — PMM prep is
  marketing-shaped), and "growth marketing" must not fall through to any
  PM growth-flavored marker.
- `"seo"`, `"ppc"` are short markers but match with non-alphanumeric
  boundaries against role strings ("seo manager", "ppc specialist") —
  safe in the resolver; the FTS concern is separate (see below).

## Role snapshot

Plans and runs measurable acquisition and retention campaigns across
search, social, email, and e-commerce channels: SEO/SEM, paid social,
email automation, content, landing-page testing, and performance
reporting in GA4. Google's certificate page cites 127,000+ open US jobs
in marketing and e-commerce and a $75,000+ median salary at 0–5 years
(https://grow.google/certificates/digital-marketing-ecommerce/ —
re-verified 2026-07-19; the earlier 213,000 figure has been revised down
on the live page). BLS: market research analysts and marketing
specialists (the closest specialist SOC) grow 7% 2024–34 with ~87,200
openings/yr and $76,950 median (May 2024)
(https://www.bls.gov/ooh/business-and-financial/market-research-analysts.htm);
advertising, promotions, and marketing managers (the promotion path) grow
6% with ~36,400 openings/yr, median $126,960 (ad/promo) and $161,030
(marketing managers)
(https://www.bls.gov/ooh/management/advertising-promotions-and-marketing-managers.htm).
Robert Half counted 376,200 US marketing and creative postings in 2025
(https://www.roberthalf.com/us/en/insights/research/data-reveals-which-marketing-and-creative-roles-are-in-highest-demand).

## Prep-process profile

- **Interview loop:** recruiter screen → portfolio/work-samples
  walkthrough (challenge → strategy → measured outcome per project) →
  channel deep-dive (SEO or paid or email, depending on the req) →
  marketing case / mock campaign (hypothetical scenario: plan the
  campaign, allocate budget, name the KPIs and expected outcomes) →
  behavioral/values round
  (https://www.tealhq.com/interview-questions/digital-marketing-specialist,
  https://jobprepped.com/digital-marketing-portfolio-guide/). Case rounds
  reward framework fluency: situation diagnosis (5 C's), STP
  (segmentation/targeting/positioning), then a 4 P's tactical plan
  (https://www.hackingthecaseinterview.com/pages/marketing-case-interview).
  The named failure mode: reciting channel definitions without tying any
  campaign to a measured business result.
- **Anchor resources:** Google Digital Marketing & E-commerce
  Professional Certificate (~6 months at 10 hrs/wk; teaches SEO, SEM,
  email, Google Ads, GA, Canva, Hootsuite, HubSpot, Mailchimp, Shopify —
  https://grow.google/certificates/digital-marketing-ecommerce/);
  Google Ads certifications on Skillshop (Search, Display, Video,
  Shopping, Apps, Measurement; 80% pass, renewed yearly —
  https://support.google.com/google-ads/answer/9702955); Google
  Analytics (GA4) certification on Skillshop; HubSpot Academy free
  certifications (Inbound Marketing, Content Marketing, Email Marketing,
  Social Media — https://academy.hubspot.com/certification-overview);
  Meta Blueprint Certified Digital Marketing Associate ($99 exam) and
  Media Buying Professional
  (https://www.facebook.com/business/learn/certification); Moz Beginner's
  Guide to SEO as the free SEO curriculum
  (https://moz.com/beginners-guide-to-seo).
- **Typical 12-week arc:** marketing funnel + SEO fundamentals and
  keyword research → Google Ads + GA4 certs with a small live or
  simulated campaign → email/social/content sprint building 2–3
  portfolio case studies → mock campaign cases with budget allocation +
  portfolio readout + behavioral.

## Seed skill entries (draft)

### Existing entries — add `digital_marketer` tag (~8)

`skill.ab-testing` (v1 — landing pages, subject lines, and creative
testing are core; `experimentation` stays on `skill.experiment-design`
per `../02-shared-entries.md`), plus these NEW·shared registry entries
defined in other profiles: `skill.google-analytics` (data-analyst.md;
owns `google analytics`, `ga4` — the single most load-bearing tool for
this track), `skill.excel` (data-analyst.md; owns `spreadsheets`),
`skill.dashboards` (data-analyst.md; owns `reporting` — campaign
reporting), `skill.metric-definition` (data-analyst.md; kpis/roas
conversations), `skill.cohort-funnel-analysis` (data-analyst.md; owns
`funnel analysis`, `retention analysis`), `skill.stakeholder-communication`
(data-analyst.md, 2°), `skill.looker` (data-analyst.md, 2° — Looker
Studio is the standard free campaign-reporting layer).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.seo` | SEO | `seo`, `search engine optimization`, `search engine optimisation`, `technical seo`, `on-page seo`, `link building`, `keyword research` | practice | digital_marketer | Top-demanded skill in postings; `seo` is short but distinctive (not an English word) |
| `skill.sem` | SEM (Paid Search) | `sem`, `search engine marketing`, `paid search` | concept | digital_marketer | `sem` is a noisy FTS token (semester, semantic…) — trust `paid search` |
| `skill.paid-media` | Paid Media & PPC | `ppc`, `pay per click`, `pay-per-click`, `paid media`, `paid advertising`, `media buying`, `retargeting`, `remarketing` | practice | digital_marketer | Channel-agnostic paid umbrella; Meta Media Buying Professional cert |
| `skill.google-ads` | Google Ads | `google ads`, `adwords`, `google adwords`, `performance max`, `youtube ads` | tool | digital_marketer | Skillshop cert anchor (Search/Display/Video/Shopping/Apps/Measurement) |
| `skill.meta-ads` | Meta Ads | `meta ads`, `facebook ads`, `instagram ads`, `meta ads manager`, `facebook advertising` | tool | digital_marketer | Meta Blueprint anchor |
| `skill.display-advertising` | Display Advertising | `display advertising`, `display ads`, `banner ads`, `programmatic advertising` | concept | digital_marketer | `dsp` deliberately NOT an alias (digital signal processing collision) |
| `skill.email-marketing` | Email Marketing | `email marketing`, `email campaigns`, `email automation`, `drip campaigns`, `newsletters`, `deliverability` | practice | digital_marketer | HubSpot Email cert; a top in-demand skill |
| `skill.mailchimp` | Mailchimp | `mailchimp` | tool | digital_marketer | Taught in the Google cert; Klaviyo/Constant Contact deferred |
| `skill.content-marketing` | Content Marketing | `content marketing`, `content strategy`, `content creation`, `content calendar` | practice | digital_marketer | HubSpot Content cert; 15% projected role growth |
| `skill.copywriting` | Copywriting | `copywriting`, `ad copy`, `marketing copywriting` | practice | digital_marketer | Portfolio-round staple |
| `skill.social-media-marketing` | Social Media Marketing | `social media marketing`, `social media`, `smm`, `social media management`, `organic social`, `community management` | practice | digital_marketer | Bare `social media` is FTS-noisy prose — advisory only |
| `skill.influencer-marketing` | Influencer Marketing | `influencer marketing`, `creator partnerships` | practice | digital_marketer | Growing posting term |
| `skill.marketing-automation` | Marketing Automation | `marketing automation`, `lead nurturing`, `lead scoring` | practice | digital_marketer | HubSpot/Marketo-flavored workflow skill |
| `skill.hubspot` | HubSpot | `hubspot`, `hubspot crm` | tool | digital_marketer | Free Academy certs make it the entry-level CRM/automation credential |
| `skill.crm` | CRM & Lead Management | `crm`, `customer relationship management`, `lead management` | concept | digital_marketer, insurance_agent(2°), financial_advisor(2°) | NEW·shared (ruled 2026-07-19): the sales tracks add-tag instead of minting CRM-tools twins; `redtail` (advisor CRM) is an optional alias candidate. `salesforce` NOT claimed (salesforce-admin.md); `lead management` won over sales-cloud's claim |
| `skill.google-tag-manager` | Google Tag Manager | `google tag manager`, `tag management`, `conversion tracking` | tool | digital_marketer | `gtm` NOT claimed (go-to-market collision) — trust the long alias |
| `skill.google-search-console` | Google Search Console | `google search console`, `search console` | tool | digital_marketer | SEO measurement counterpart to GA4 |
| `skill.conversion-rate-optimization` | Conversion Rate Optimization | `conversion rate optimization`, `conversion optimization`, `cro`, `landing pages`, `landing page optimization` | concept | digital_marketer | Pairs with `skill.ab-testing`; `cro` is noisy — trust long alias |
| `skill.marketing-analytics` | Marketing Analytics | `marketing analytics`, `campaign analytics`, `utm tracking`, `utm parameters`, `roas` | concept | digital_marketer | 19% of new digital-marketing postings are analytics-flavored |
| `skill.attribution` | Marketing Attribution | `attribution modeling`, `marketing attribution`, `multi-touch attribution`, `attribution` | concept | digital_marketer | Bare `attribution` is English-word-noisy — trust the modeling aliases |
| `skill.customer-segmentation` | Customer Segmentation | `customer segmentation`, `audience segmentation`, `market segmentation`, `audience targeting` | concept | digital_marketer | Bare `segmentation` deliberately NOT claimed (ML image-segmentation collision) |
| `skill.marketing-funnel` | Marketing Funnel | `marketing funnel`, `sales funnel` | concept | digital_marketer | `funnel analysis` stays on `skill.cohort-funnel-analysis`; `customer journey` CONTESTED with UX |
| `skill.demand-generation` | Demand Generation | `demand generation`, `demand gen`, `growth marketing`, `growth hacking` | practice | digital_marketer | B2B-flavored umbrella; posting language. Ruled 2026-07-19: `lead generation`/`lead gen` live on `skill.prospecting` (financial-advisor.md, sales cluster) — marketing keeps the demand-gen forms |
| `skill.brand-marketing` | Brand Marketing | `brand marketing`, `branding`, `brand awareness` | concept | digital_marketer | Case-round vocabulary |
| `skill.ecommerce` | E-commerce | `ecommerce`, `e-commerce`, `online store` | concept | digital_marketer | Half the Google certificate's title |
| `skill.shopify` | Shopify | `shopify` | tool | digital_marketer | Taught in the Google cert e-commerce module |
| `skill.wordpress` | WordPress | `wordpress`, `cms`, `content management system` | tool | digital_marketer | Dominant CMS; `cms` reasonably distinctive |
| `skill.canva` | Canva | `canva` | tool | digital_marketer | Marketer's design tool (Figma stays UX/PM) |

**Optional / deferred** (protect the ≤100 budget; add only if enrichment
or user demand supports them): Semrush/Ahrefs/Moz as an SEO-tools entry,
Hootsuite/Buffer/Sprout Social scheduling tools, Klaviyo, Constant
Contact, LinkedIn Ads, TikTok Ads/marketing, video marketing / YouTube
marketing as a distinct entry, affiliate marketing, PR/communications,
Marketo (adobe stack), webinars/events.

Tally: ~28 new + ~8 existing/registry tags ≈ **36 entries** — well under
the ~55 self-cap and ~100 prompt budget.

## Alias-collision & FTS5 notes

- `google analytics`, `ga4` → already homed on `skill.google-analytics`
  (registry, data-analyst.md). `a/b testing`, `ab testing` → v1
  `skill.ab-testing`. `experimentation` → ruled to
  `skill.experiment-design`. `funnel analysis`, `retention analysis` →
  `skill.cohort-funnel-analysis`. `reporting`, `dashboards` →
  `skill.dashboards`. `kpis` → `skill.metric-definition`.
  `spreadsheets` → `skill.excel`. `google data studio`, `looker studio`
  → `skill.looker`. Tag those entries; mint nothing.
- **`salesforce` NOT claimed**: a `salesforce_admin` track is being
  drafted in parallel and owns it. This track's CRM story lives on
  `skill.crm` + `skill.hubspot`. `pardot` / `salesforce marketing cloud`
  also left to that track. CONTESTED only if reconciliation decides
  marketers need a resolvable `salesforce` surface.
- **`gtm` NOT claimed**: collides with "go-to-market" (product_manager
  territory). `skill.google-tag-manager` relies on its long aliases.
  CONTESTED — whichever side wants the bare token must win it centrally.
- **`customer journey` / `journey mapping` NOT claimed**: likely UX
  territory (`skill.user-flows` neighborhood). This track keeps
  `marketing funnel` / `sales funnel`. CONTESTED.
- Bare `segmentation` NOT claimed (future ML image-segmentation
  collision); bare `analytics`, `email`, `content`, `funnel`, `social`
  treated as deliberately homeless.
- Short/noisy FTS tokens: `sem` (→ trust `search engine marketing` /
  `paid search`), `cro` (→ `conversion rate optimization`), `smm`
  (→ `social media marketing`), bare `attribution` and `social media`
  (English-prose noise → trust `attribution modeling` / the full
  channel phrases), `branding`/`brand awareness` (prose-common —
  advisory counts). `seo`, `ppc`, `crm`, `cms` are short but
  distinctive enough to keep.
- Aliases here are post-normalization legal: lowercase, internal
  `/`/`-` preserved, no trailing periods.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://grow.google/certificates/digital-marketing-ecommerce/ | role_taxonomy | Canonical entry-cert landing (jobs/salary stats churn — 213k→127k between checks) |
| https://www.coursera.org/professional-certificates/google-digital-marketing-ecommerce | role_taxonomy | Course-level syllabus of the same cert; occasionally restructured |
| https://support.google.com/google-ads/answer/9702955 | role_taxonomy | Official "About Google Ads certifications" (Search/Display/Video/Shopping/Apps/Measurement); stable |
| https://skillshop.exceedlms.com/student/catalog/list?category_ids=2844-google-ads-certifications | role_taxonomy | Skillshop cert catalog; URL-churn risk (platform migrating to docebo) |
| https://academy.hubspot.com/certification-overview | role_taxonomy | HubSpot Academy free cert list (inbound/content/email/social); stable |
| https://www.facebook.com/business/learn/certification | role_taxonomy | Meta Blueprint cert exams (Digital Marketing Associate, Media Buying Professional); stable |
| https://www.bls.gov/ooh/business-and-financial/market-research-analysts.htm | role_taxonomy | Closest specialist SOC (7%, 87.2k openings/yr); bls.gov 403s non-browser fetchers — ingestion needs a browser UA or manual snapshot |
| https://www.bls.gov/ooh/management/advertising-promotions-and-marketing-managers.htm | role_taxonomy | Manager-path outlook (6%, 36.4k/yr); same 403 caveat |
| https://moz.com/beginners-guide-to-seo | role_taxonomy | Canonical free SEO curriculum; stable for a decade |
| https://digitalmarketinginstitute.com/blog/the-ultimate-digital-marketing-interview-checklist | interview_report | Interview checklist from a cert body; refreshed yearly |
| https://www.tealhq.com/interview-questions/digital-marketing-specialist | interview_report | Role-specific question bank + loop shape; yearly refresh |
| https://brainstation.io/career-guides/digital-marketing-interview-questions | interview_report | Question bank with channel deep-dive framing |
| https://www.hackingthecaseinterview.com/pages/marketing-case-interview | interview_report | Marketing case frameworks (5C/STP/4P); stable |
| https://jobprepped.com/digital-marketing-portfolio-guide/ | role_taxonomy | Portfolio-expectation stats (78%/63%); smaller-site link-rot risk |
| (job boards: linkedin/indeed digital-marketing-specialist searches) | official_job_posting | Volatile + login-gated; sample per run |

## Enrichment expectations

Expect `seo`, `google analytics`, `social media`, `email marketing`,
`content marketing`, `google ads` to dominate counts (with `social
media` inflated by prose — read the per-alias breakdown). Zero-support
flags likely for `canva`, `shopify`, `google search console`, `demand
generation` (tool names and B2B phrasing are thin in cert-page prose) —
keep them; résumé-resolution value stands on its own. `branding` and
`attribution` counts are advisory only.

## Overlap with existing tracks

The analytics slice (google-analytics, dashboards, metric-definition,
cohort-funnel, excel, looker) is shared with `data_analyst` and
`product_manager` by design — measurement is the marketer's credibility
skill. Boundary with `product_manager`: PM owns go-to-market strategy
and product-sense casework; this track owns channel execution — the
shared entries (`skill.metric-definition`, `skill.google-analytics`)
carry both tags. Boundary with `ux_designer`: UX owns journey/flow
artifacts; marketing owns funnel vocabulary. Boundary with the parallel
`salesforce_admin` draft: admins own the Salesforce platform vocabulary;
marketers keep `crm`/`hubspot`. Effectively zero overlap with `swe`,
`mle`, and the infra tracks.
