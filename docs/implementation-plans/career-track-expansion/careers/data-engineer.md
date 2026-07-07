# Data Engineer — Track Profile

**Proposed enum value:** `data_engineer` · **Wave 1** · Research grounded
2026-07-06.

## Track decision

Own track. Closest of the data careers to `swe` (DDIA is canon for both;
python/java, ci/cd, docker, distributed systems shared), but the loop has
rounds `swe` prep never covers: data modeling (schemas, grain, SCDs),
pipeline/ETL design, and data-architecture design with warehouse/streaming
tradeoffs. Distinct cert spine (AWS DEA-C01, DP-700, GCP PDE, Databricks,
SnowPro) confirms a separately codified path.

**Resolver markers:** `"data engineer"`, `"data engineering"`,
`"analytics engineer"` (judgment call: the dbt-centric middle role — 48%
of dbt's survey population — sits between DE and DA; homing it in
`data_engineer` keeps dbt/warehouse vocabulary in scope), `"etl
developer"`, `"data platform"`, `"big data engineer"`.

## Role snapshot

Designs, builds, and operates pipelines, warehouses/lakehouses, and
streaming systems (https://roadmap.sh/data-engineer). 84k+ US LinkedIn
postings; WEF projects ~100% growth for big-data specialists 2025–2030;
role counts grew ~23% in 2025
(https://365datascience.com/career-advice/data-engineer-job-outlook-2025/).
Technical prep is well-codified (cert syllabi + canonical book + a free
canonical curriculum); loop structure varies more by company (3–9 rounds)
than DA/DS.

## Prep-process profile

- **Interview loop:** recruiter screen → SQL/Python screen (window
  functions, dedup, gap-and-islands) → take-home or live ETL coding
  (production-readiness over leetcode depth) → onsite: SQL deep-dive, data
  modeling (star schema, grain, SCDs, partitioning), pipeline/ETL design,
  data-architecture system design (ingestion→ELT→streaming→orchestration→
  quality, with cost/latency tradeoffs), behavioral/ownership
  (https://www.interviewquery.com/p/data-engineer-interview-questions).
  Recommended answer skeleton: assumptions → pipeline design → tradeoffs →
  failure points → monitoring/validation.
- **Anchor resources:** *Designing Data-Intensive Applications*
  (https://dataintensive.net/ — 2nd ed. 2026); AWS Data Engineer Associate
  DEA-C01 (ingestion & transformation 34%, store management 26%, ops 22%,
  security 18%); Microsoft DP-700 (Fabric; replaced DP-203, retired
  2025-03); GCP Professional Data Engineer; Databricks DE Associate;
  SnowPro; and the free **Data Engineering Zoomcamp** (~9 weeks:
  Docker/Terraform → orchestration → BigQuery → dbt → Spark → Kafka —
  https://github.com/DataTalksClub/data-engineering-zoomcamp).
- **Typical arc** (a real 8-week Amazon-DE prep: ~150 LeetCode, DDIA
  cover-to-cover, 3 end-to-end AWS pipelines, design mocks 2×/wk):
  advanced SQL + python → data modeling + one warehouse → batch/
  orchestration/streaming concepts + portfolio pipelines → design mocks +
  quality/monitoring talking points + behavioral.

## Seed skill entries (draft)

Frequency grounding: SQL and Python in ~94% of DE postings, dbt 61%,
Airflow 58% (dbt Labs State of Analytics Engineering via
https://jobstrack.io/blog/roles/data-engineer).

### Existing entries — add `data_engineer` tag (~25)

`skill.sql`, `skill.python`, `skill.java`, `skill.scala`, `skill.bash`,
`skill.linux`, `skill.git`, `skill.spark` (has `pyspark`),
`skill.kafka`, `skill.airflow`, `skill.dbt`, `skill.bigquery`,
`skill.snowflake`, `skill.postgresql`, `skill.mysql`, `skill.mongodb`,
`skill.dynamodb`, `skill.cassandra`, `skill.redis`, `skill.docker`,
`skill.kubernetes`, `skill.terraform`, `skill.aws`, `skill.gcp`,
`skill.ci-cd`, `skill.testing`, `skill.observability`,
`skill.distributed-systems`, `skill.system-design`,
`skill.data-pipelines` (owns `etl`, `data pipelines` — consider adding
alias `elt`), `skill.database-design` (owns `data modeling`),
`skill.event-driven`, `skill.rest-apis`, `skill.data-structures`,
`skill.algorithms`, `skill.agile`, `skill.code-review`.

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.data-warehousing` | Data Warehousing | `data warehouse`, `data warehousing`, `olap` | concept | data_engineer, data_analyst | NEW·shared; core destination architecture |
| `skill.data-lake` | Data Lakes & Lakehouses | `data lake`, `lakehouse`, `medallion architecture` | concept | data_engineer | Modern storage vocabulary |
| `skill.dimensional-modeling` | Dimensional Modeling | `dimensional modeling`, `star schema`, `kimball`, `slowly changing dimensions`, `scd` | concept | data_engineer, data_analyst | Dedicated interview round; bare `data modeling` stays on `skill.database-design` |
| `skill.stream-processing` | Stream Processing | `stream processing`, `streaming`, `real-time data` | concept | data_engineer | Distinguishes senior/streaming roles |
| `skill.orchestration` | Workflow Orchestration | `workflow orchestration`, `orchestration`, `dags`, `backfill` | concept | data_engineer | How pipelines run reliably; Airflow/dagster are the tools |
| `skill.incremental-loads` | Incremental Loads & Idempotency | `incremental loading`, `incremental models`, `upsert`, `merge`, `idempotent` | concept | data_engineer | Distinguishes production-grade candidates |
| `skill.cdc` | Change Data Capture | `change data capture`, `cdc`, `debezium` | concept | data_engineer | Standard replication pattern; secondary |
| `skill.columnar-formats` | File Formats & Columnar Storage | `parquet`, `avro`, `orc`, `columnar storage` | concept | data_engineer | Storage-choice interview questions |
| `skill.partitioning` | Partitioning & Query Optimization | `partitioning`, `partition pruning`, `query optimization`, `indexing` | concept | data_engineer | Warehouse cost/perf questions |
| `skill.data-governance` | Data Governance | `data governance`, `data lineage`, `data catalog`, `metadata management`, `pii handling` | concept | data_engineer | 18% of DEA-C01; bare `pii` left out (too generic) |
| `skill.data-contracts` | Data Quality Tooling | `data contracts`, `great expectations`, `data testing`, `data observability` | practice | data_engineer | Top pain point (56% in dbt survey); bare `data quality` lives on `skill.data-quality` (see data-analyst.md) |
| `skill.redshift` | Amazon Redshift | `redshift`, `amazon redshift` | tool | data_engineer | AWS warehouse; secondary |
| `skill.flink` | Apache Flink | `flink`, `apache flink` | framework | data_engineer | Real-time streaming; secondary |
| `skill.hadoop` | Hadoop Ecosystem | `hadoop`, `hdfs`, `hive`, `mapreduce` | framework | data_engineer | Legacy but still posted; secondary |
| `skill.s3` | Object Storage (S3) | `s3`, `object storage` | tool | data_engineer, cloud_engineer | NEW·shared; de facto data-lake layer |
| `skill.dagster-prefect` | Dagster / Prefect | `dagster`, `prefect` | tool | data_engineer | Modern orchestrator alternatives; secondary |
| `skill.fivetran-airbyte` | Managed Connectors | `fivetran`, `airbyte` | tool | data_engineer | Modern-stack EL(T) ingestion; secondary |
| `skill.dataops` | DataOps | `dataops` | practice | data_engineer | Named umbrella practice; secondary |

Shared NEW entries defined elsewhere that also tag `data_engineer`:
`skill.window-functions`, `skill.data-quality`, `skill.data-cleaning`
(secondary), `skill.databricks` (defined in data-scientist.md),
`skill.infrastructure-as-code` (defined in devops-sre.md, secondary tag).

**Optional / deferred:** AWS Glue, Kinesis, Azure Data Factory / Fabric
(`adf`, `microsoft fabric`, `synapse` — core only in Azure shops), Beam/
Dataflow, CAP-theorem entry (`cap theorem`, `eventual consistency`, `acid`
— defensible `concept`, also arguable `swe`; curation call).

## Alias-collision & FTS5 notes

- `etl`/`data pipelines` (on `skill.data-pipelines`), `data modeling` (on
  `skill.database-design`), `spark`/`pyspark`, `airflow`, `dbt`,
  `snowflake`, `bigquery` — all existing; tag, don't mint.
- `streaming` is a noisy FTS token (video streaming, event streaming
  prose); trust `stream processing` counts.
- `merge`/`upsert` are SQL keywords that appear constantly in technical
  corpus prose — expect inflated counts on `skill.incremental-loads`;
  interpret via `incremental loading`/`incremental models`.
- `hive` collides with ordinary English ("hive of activity") — minor, but
  note it.
- `data quality` has one home (`skill.data-quality`, shared with
  data_analyst); the DE-specific tooling entry uses `data contracts` etc.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://roadmap.sh/data-engineer | role_taxonomy | Open-source skill tree; stable |
| https://docs.aws.amazon.com/aws-certification/latest/examguides/data-engineer-associate-01.html | role_taxonomy | Official DEA-C01 domains/weights (PDF mirror exists); ~3-yr rev cycle |
| https://learn.microsoft.com/en-us/credentials/certifications/fabric-data-engineer-associate/ | role_taxonomy | Official DP-700 (supersedes retired DP-203); stable |
| https://cloud.google.com/learn/certification/data-engineer | role_taxonomy | GCP PDE scope + exam-guide PDF |
| https://www.databricks.com/learn/certification/data-engineer-associate | role_taxonomy | Lakehouse-stack skill definition |
| https://learn.snowflake.com/en/certifications/ | role_taxonomy | SnowPro domain lists |
| https://github.com/DataTalksClub/data-engineering-zoomcamp | role_taxonomy | Free canonical 9-week curriculum; open-source, very stable |
| https://dataintensive.net/ | role_taxonomy | DDIA scope (TOC-level; book text copyrighted) |
| https://www.interviewquery.com/p/data-engineer-interview-questions | interview_report | 150+ categorized questions; partial paywall |
| https://www.interviewquery.com/interview-guides/amazon-data-engineer | interview_report | Amazon-specific round breakdown |
| https://medium.com/@rasterroo/meta-data-engineer-interview-experience-2025-c26d23f995ce | interview_postmortem | First-person Meta DE onsite; Medium volatility |
| https://medium.com/towards-data-engineering/my-amazon-data-engineering-interview-experience-what-i-learned-from-getting-rejected-2025-fd2f88f40a17 | interview_postmortem | Honest rejection postmortem incl. exact 8-week plan |
| https://www.getdbt.com/resources/state-of-analytics-engineering-2025 | role_taxonomy | Annual practitioner survey; download may be email-gated (blog summary open) |
| https://www.montecarlodata.com/blog-data-engineering-architecture/ | company_engineering_blog | Digest of Netflix/Uber/Airbnb data-platform posts; vendor framing caveat |

## Enrichment expectations

`sql`, `python`, `spark`, `airflow`, `dbt`, `etl`, `data warehouse`
should dominate. `debezium`, `dagster`, `fivetran` likely low-support —
fine, they're secondary. If `dimensional modeling`/`star schema` come back
zero, the corpus lacks modeling content (a Kimball-adjacent explainer or
the Zoomcamp warehouse module fixes it).

## Overlap with existing tracks

vs `swe`: highest overlap of the data trio (git, ci/cd, testing, docker,
distributed systems, system design); DE-distinctive: sql depth, modeling,
warehouses, orchestration, batch/stream semantics. vs `mle`: converges on
feature/data pipelines ("data for AI" demand); MLE keeps training/serving.
vs `data_analyst`: DE builds what DA consumes; skills barely cross loops
in either direction (https://roadmap.sh/data-analyst/vs-data-engineer).
