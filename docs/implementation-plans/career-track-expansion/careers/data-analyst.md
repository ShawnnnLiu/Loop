# Data Analyst — Track Profile

**Proposed enum value:** `data_analyst` · **Wave 1** · Research grounded
2026-07-06.

## Track decision

Own track — the most codified prep process of any career researched: one
dominant entry certificate (Google Data Analytics), a standardized
SQL-screen-plus-case loop, and mature question banks (DataLemur,
StrataScratch, Interview Query). Skill set is far from `swe` (no DS&A, no
system design) and distinct from `mle` (BI tools and business casework vs
modeling).

**Resolver markers:** `"data analyst"`, `"data analytics"`,
`"business intelligence"`, `"bi analyst"`, `"analytics"`,
`"reporting analyst"`, `"product analyst"`. Insert before any
data-scientist markers only if none collide; "product analyst" is a
judgment call (some are DS-shaped) — precedence review needed at
implementation time. Ruled 2026-07-19: `"business analyst"` re-homed to
the `business_analyst` track (business-analyst.md) — its marker tuple
must precede this one; DA keeps the BI-flavored markers.

## Role snapshot

Extracts, cleans, and visualizes business data (SQL, Excel, BI tools) to
answer stakeholder questions; queries, dashboards, and reports rather than
model building (https://roadmap.sh/data-analyst). Very high volume: 97k+
US LinkedIn postings; adjacent BLS analyst occupations grow 7–21%
(2024–34) vs 3% average
(https://www.bls.gov/ooh/math/operations-research-analysts.htm).

## Prep-process profile

- **Interview loop:** recruiter screen → timed SQL assessment (joins,
  aggregations, window functions, CTEs) → analytics case study (metric
  movement, product change; often a multi-day take-home with a panel
  readout) → dashboard/visualization round → behavioral. The named failure
  mode: treating it as a SQL exam when it is a business problem-solving
  interview (https://www.tryexponent.com/blog/data-analyst-interview-guide).
- **Anchor resources:** Google Data Analytics Professional Certificate
  (~6 months, the de facto entry credential —
  https://www.coursera.org/professional-certificates/google-data-analytics);
  Microsoft PL-300 with published domain weights (prepare data 25–30%,
  model with DAX 25–30%, visualize 25–30%, manage 15–20% —
  https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/pl-300);
  Tableau Desktop Specialist; Mode SQL Tutorial; DataLemur/StrataScratch
  drills.
- **Typical 12-week arc:** SQL through window functions → Excel + one BI
  tool + portfolio dashboards → stats/hypothesis-testing/A-B literacy +
  metric casework → full mock cases with presented readouts + behavioral.

## Seed skill entries (draft)

Frequency grounding: SQL in ~45–51% of DA postings, Excel ~32%, Python
~31%, Power BI ~28% (https://datanerd.tech/).

### Existing entries — add `data_analyst` tag (~12)

`skill.sql`, `skill.python`, `skill.r`, `skill.git`, `skill.statistics`
(consider adding alias `descriptive statistics`), `skill.ab-testing`
(consider aliases `split testing`, `experimentation` — see
`../02-shared-entries.md`), `skill.time-series` (has `forecasting`),
`skill.database-design` (owns alias `data modeling`), `skill.bigquery`,
`skill.snowflake`, `skill.jupyter`, `skill.agile`,
`skill.data-pipelines` (owns alias `etl` — analysts consume pipelines).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.excel` | Excel | `excel`, `microsoft excel`, `ms excel`, `spreadsheets`, `pivot tables`, `vlookup` | tool | data_analyst | ~32% of postings; business lingua franca |
| `skill.power-bi` | Power BI | `power bi`, `powerbi`, `pbi`, `dax`, `power query` | tool | data_analyst | ~28% of postings; PL-300 anchor. Folding `dax`/`power query` in is a curation call |
| `skill.tableau` | Tableau | `tableau`, `tableau desktop`, `tableau public` | tool | data_analyst, data_scientist | NEW·shared; own cert track |
| `skill.looker` | Looker | `looker`, `lookml`, `looker studio`, `google data studio` | tool | data_analyst | GCP-shop BI |
| `skill.google-sheets` | Google Sheets | `google sheets`, `gsheets` | tool | data_analyst | Startup/SMB standard; secondary |
| `skill.data-visualization` | Data Visualization | `data visualization`, `data visualisation`, `data viz`, `dataviz` | concept | data_analyst, data_scientist | NEW·shared; the analyst's output medium |
| `skill.dashboards` | Dashboards & Reporting | `dashboards`, `dashboarding`, `kpi dashboards`, `ad hoc reporting`, `reporting` | practice | data_analyst | What most DA jobs ship weekly |
| `skill.business-intelligence` | Business Intelligence | `business intelligence`, `bi` | concept | data_analyst | `bi` is a short/noisy FTS token — trust the long alias |
| `skill.hypothesis-testing` | Hypothesis Testing | `hypothesis testing`, `significance testing`, `p-value`, `confidence intervals`, `t-test` | concept | data_analyst, data_scientist | NEW·shared; case-round staple |
| `skill.eda` | Exploratory Data Analysis | `exploratory data analysis`, `eda` | concept | data_analyst, data_scientist | NEW·shared; first step of every take-home |
| `skill.data-cleaning` | Data Cleaning | `data cleaning`, `data wrangling`, `data preparation`, `data preprocessing` | practice | data_analyst, data_scientist | NEW·shared; bulk of real analyst time |
| `skill.window-functions` | SQL Window Functions | `window functions`, `analytic functions` | concept | data_analyst, data_scientist, data_engineer | NEW·shared; the discriminator in SQL screens |
| `skill.metric-definition` | KPIs & Metric Definition | `kpis`, `key performance indicators`, `metric definition`, `business metrics`, `north star metric` | concept | data_analyst, data_scientist, product_manager | NEW·shared; dashboard-round judgment |
| `skill.cohort-funnel-analysis` | Cohort & Funnel Analysis | `cohort analysis`, `funnel analysis`, `retention analysis` | concept | data_analyst, data_scientist, product_manager | NEW·shared; product-analytics case pattern |
| `skill.data-storytelling` | Data Storytelling | `data storytelling`, `storytelling with data`, `insight communication` | practice | data_analyst, data_scientist, product_manager | NEW·shared; readouts are judged on narrative |
| `skill.stakeholder-communication` | Stakeholder Communication | `stakeholder management`, `stakeholder communication`, `cross-functional collaboration`, `presentation skills` | practice | data_analyst, data_scientist, product_manager | NEW·shared; in nearly every posting |
| `skill.data-quality` | Data Quality | `data quality`, `data validation`, `data integrity` | practice | data_analyst, data_engineer | NEW·shared; "what if the data is wrong" probe |
| `skill.requirements-gathering` | Requirements Gathering | `requirements gathering`, `business requirements` | practice | data_analyst | Turning vague asks into queries |
| `skill.google-analytics` | Google Analytics | `google analytics`, `ga4` | tool | data_analyst, product_manager | NEW·shared; marketing/product variants |
| `skill.regression-analysis` | Regression Analysis | `linear regression`, `logistic regression`, `regression` | concept | data_analyst, data_scientist | NEW·shared; also first-asked DS ML question |

**Optional / deferred** (protect the ≤100 budget; add only if enrichment
or user demand supports them): VBA/macros, SSIS/SSRS, Qlik, Alteryx,
SQL Server as a distinct entry (`t-sql`/`mssql` aliases), Power Query as
its own entry.

## Alias-collision & FTS5 notes

- `etl`, `data pipelines` → already on `skill.data-pipelines`; `data
  modeling` → already on `skill.database-design`; `forecasting` → already
  on `skill.time-series`. Tag those entries rather than minting new ones.
- `spreadsheets` lives on `skill.excel` only (not Google Sheets).
- `bi` and `eda` are short tokens; rely on the long aliases for
  enrichment interpretation. `r` (existing) is unusable for FTS counting —
  known limitation.
- `documentation` is deliberately homeless: too generic to resolve to one
  skill (analyst docs vs runbooks vs design specs).

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://roadmap.sh/data-analyst | role_taxonomy | Community skill tree; stable, PDF variant exists |
| https://www.coursera.org/professional-certificates/google-data-analytics | role_taxonomy | Canonical entry-cert syllabus; marketing page, occasionally restructured |
| https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/pl-300 | role_taxonomy | Official PL-300 skills-measured; stable, permissively licensed |
| https://www.tableau.com/learn/certification/desktop-specialist | role_taxonomy | Official Tableau cert scope; Salesforce URL churn risk |
| https://mode.com/sql-tutorial/sql-in-mode/index.html | role_taxonomy | Canonical free analyst SQL curriculum; stable for years |
| https://www.tryexponent.com/blog/data-analyst-interview-guide | role_taxonomy | Loop-stage breakdown; refreshed yearly |
| https://careerservices.fas.harvard.edu/blog/2025/05/05/data-analyst-interview-prep-2025-guide/ | role_taxonomy | Neutral university prep guide; stable |
| https://www.interviewquery.com/p/sql-questions-data-analyst | interview_report | Real DA SQL patterns; partial paywall |
| https://datalemur.com/questions | interview_report | FAANG SQL/analytics bank; partial paywall |
| https://www.stratascratch.com/blog/sql-interview-questions-for-the-data-analyst-position | interview_report | Company-attributed questions |
| https://www.datacamp.com/blog/how-to-prepare-for-a-data-analyst-interview | interview_report | 25-question prep guide; refreshed yearly |
| https://datanerd.tech/ | role_taxonomy | Skill-frequency analytics over 4M+ postings; data volatile by design |
| (job boards: linkedin/indeed data-analyst searches) | official_job_posting | Volatile + login-gated; sample per run |

## Enrichment expectations

Expect `sql`, `excel`, `power bi`, `tableau`, `dashboards`, `data
visualization` to dominate counts. Zero-support flags likely for
`requirements gathering` and `google sheets` (prose about them uses varied
phrasing) — keep them; the résumé-resolution value stands on its own.

## Overlap with existing tracks

Minimal overlap with `swe` (sql, git, some python — no DS&A, no system
design). Nearly disjoint from `mle` except python/sql/statistics. DA is
roughly the analytics subset of data scientist — see
`data-scientist.md`; the two tracks share ~15 entries by design.
