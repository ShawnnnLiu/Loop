# Data Scientist — Track Profile

**Proposed enum value:** `data_scientist` · **Wave 1** · Research grounded
2026-07-06.

## Track decision

Own track. Largest pairwise overlap is with `mle` (python, ML theory,
scikit-learn, model evaluation), but the prep processes differ materially:
DS loops center on statistics/probability, experiment design, and product
sense (the Meta "analytical execution" round is the archetype); MLE loops
center on serving, MLOps, and engineering rigor. Per the granularity
policy, different loop stages ⇒ different track.

**Resolver markers:** `"data scientist"`, `"data science"`,
`"product data scientist"`, `"decision scientist"`, `"quantitative
analyst"` (judgment call — quant finance is its own world; acceptable
approximation for now). Must be checked **before** `mle`'s marker set is
consulted for strings like "ml scientist"? No — `mle` markers stay first;
"data scientist" does not collide with them.

## Role snapshot

Combines statistics, ML, and programming to extract insight and build
predictive models. BLS projects **34% growth 2024–2034** (4th
fastest-growing US occupation, median $112,590 —
https://www.bls.gov/ooh/math/data-scientists.htm); 139k+ US LinkedIn
"data science" jobs. Prep is well-codified at the top of the market
(standard 4–5-round loop, a canonical book, dedicated platforms) but
spans six question domains with no single dominant certification.

## Prep-process profile

- **Interview loop** (Meta pattern is canonical for product DS): recruiter
  screen → technical screen (live SQL/Python + stats/ML fundamentals) →
  sometimes a take-home → final loop of 4–5 rounds: analytical reasoning
  (stats/probability/foundational ML), analytical execution (metric
  design, experiment diagnosis, A/B tests), SQL/coding, behavioral
  (https://igotanoffer.com/blogs/tech/facebook-data-scientist-interview).
  Question frequency: SQL in >90% of DS interviews, ML ~85%, Python ~80%
  (https://www.interviewquery.com/learning-paths/data-science-interview/introduction-to-data-science/overview-of-the-data-science-learning-path).
- **Anchor resources:** *Ace the Data Science Interview* (201 real
  questions across probability, statistics, ML, SQL, coding, product
  sense — the closest thing to a canonical prep book,
  https://www.acethedatascienceinterview.com/); DataLemur; Interview Query
  DS learning path; Exponent. Certs are secondary; Google Advanced Data
  Analytics Certificate is the most-cited structured curriculum.
- **Typical arc:** ~3 months at ~11 hrs/wk recommended
  (https://www.datacamp.com/blog/data-science-interview-preparation):
  Python+SQL drills → stats & probability review → ML concepts &
  evaluation → product/experimentation cases → mocks + behavioral.

## Seed skill entries (draft)

Frequency grounding: Python in 57–86% of postings, ML ~65–69%, R 33%, SQL
30%+, NLP 19% and rising
(https://365datascience.com/career-advice/career-guides/data-scientist-job-outlook-2025/).

### Existing entries — add `data_scientist` tag (~25)

The `mle` track already paid for most of this career's vocabulary:
`skill.python`, `skill.sql`, `skill.r`, `skill.git`, `skill.pandas`,
`skill.numpy`, `skill.scikit-learn`, `skill.xgboost`, `skill.lightgbm`,
`skill.statistics`, `skill.probability`, `skill.machine-learning`,
`skill.deep-learning`, `skill.pytorch`, `skill.tensorflow`, `skill.keras`,
`skill.feature-engineering`, `skill.model-evaluation` (consider aliases
`cross-validation`, `cross validation`), `skill.nlp`, `skill.llms` (tag —
GenAI-flavored DS is the fastest-growing posting cluster),
`skill.time-series`, `skill.recommendation-systems`, `skill.spark`,
`skill.jupyter` (consider aliases `google colab`, `colab`),
`skill.bigquery`, `skill.snowflake`, `skill.sagemaker`, `skill.mlflow`,
`skill.airflow`, `skill.docker`, `skill.ab-testing`, `skill.embeddings`
(has `pca`-adjacent meaning? no — keep; see collisions),
`skill.data-structures`, `skill.algorithms` (light coding screens).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.experiment-design` | Experiment Design | `experiment design`, `experimentation`, `online experiments`, `controlled experiments` | concept | data_scientist, product_manager | NEW·shared; the signature product-DS round. Alternative: fold into `skill.ab-testing` aliases — curation call, one home only |
| `skill.causal-inference` | Causal Inference | `causal inference`, `difference-in-differences`, `propensity score matching` | concept | data_scientist | Senior product-DS differentiator |
| `skill.bayesian-statistics` | Bayesian Statistics | `bayesian statistics`, `bayesian inference`, `bayesian` | concept | data_scientist | Senior/quant-flavored rounds |
| `skill.regularization` | Regularization & Bias-Variance | `regularization`, `overfitting`, `bias-variance tradeoff`, `lasso`, `ridge` | concept | data_scientist | Canonical conceptual question |
| `skill.clustering` | Clustering | `clustering`, `k-means`, `kmeans`, `unsupervised learning`, `segmentation` | concept | data_scientist | Standard concept-round content |
| `skill.classification` | Classification | `classification`, `classifiers`, `random forest`, `decision trees`, `ensemble methods` | concept | data_scientist | Most-used practical model family; bundling tree ensembles here is a curation call |
| `skill.dimensionality-reduction` | Dimensionality Reduction | `dimensionality reduction`, `pca`, `principal component analysis` | concept | data_scientist | Concept-round staple |
| `skill.product-sense` | Product Sense | `product sense`, `product intuition`, `product thinking`, `product analytics` | concept | data_scientist, product_manager | NEW·shared; Meta-style execution round / PM's own round |
| `skill.statsmodels` | statsmodels | `statsmodels` | framework | data_scientist | Inference-grade regression; secondary |
| `skill.matplotlib` | Matplotlib | `matplotlib`, `pyplot` | framework | data_scientist, data_analyst | NEW·shared; default Python charting |
| `skill.seaborn` | Seaborn | `seaborn` | framework | data_scientist | EDA plots; secondary |
| `skill.plotly` | Plotly | `plotly`, `plotly dash` | framework | data_scientist | Interactive viz; secondary |
| `skill.databricks` | Databricks | `databricks`, `delta lake` | tool | data_scientist, data_engineer | NEW·shared; folding `delta lake` in is a curation call |
| `skill.kaggle` | Kaggle & Portfolio Projects | `kaggle`, `kaggle competitions`, `portfolio projects` | practice | data_scientist | Standard entry-path evidence |

Shared NEW entries defined in `data-analyst.md` that also tag
`data_scientist`: `skill.tableau`, `skill.data-visualization`,
`skill.hypothesis-testing`, `skill.eda`, `skill.data-cleaning`,
`skill.window-functions`, `skill.metric-definition`,
`skill.cohort-funnel-analysis`, `skill.data-storytelling`,
`skill.stakeholder-communication`, `skill.regression-analysis`,
`skill.power-bi` (secondary tag).

**Optional / deferred:** Scala (exists, `mle`-tagged — tag only if
enrichment supports), Azure ML, Hugging Face (exists — tag is defensible),
`arima`/`prophet` as time-series aliases.

## Alias-collision & FTS5 notes

- `machine learning`, `ml`, `deep learning`, `neural networks`,
  `statistics`, `probability`, `feature engineering`, `mlops` — all
  already owned by `mle`-tagged entries; tag, don't mint.
- `experimentation` can live on either `skill.ab-testing` or the new
  `skill.experiment-design` — **one home only**; recommendation: the new
  entry (finer-grained), keeping `a/b testing`/`ab testing` where they
  are. Recorded in `../02-shared-entries.md`.
- `random forest`/`decision trees` bundled under `skill.classification`
  rather than separate entries — curation call to protect the budget.
- `pca` is a short token but rare in ordinary prose — acceptable.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://www.bls.gov/ooh/math/data-scientists.htm | role_taxonomy | Authoritative outlook/duties; public domain, very stable |
| https://roadmap.sh/ai-data-scientist | role_taxonomy | Open-source skill tree; stable |
| https://www.acethedatascienceinterview.com/ | role_taxonomy | Canonical prep book's topic breakdown; book text copyrighted — site only |
| https://www.interviewquery.com/learning-paths/data-science-interview/introduction-to-data-science/overview-of-the-data-science-learning-path | role_taxonomy | Codified 4-module prep taxonomy + question-frequency stats; partial paywall |
| https://www.tryexponent.com/blog/data-science-interview-guide | role_taxonomy | Loop stages; refreshed yearly |
| https://igotanoffer.com/blogs/tech/facebook-data-scientist-interview | interview_report | Meta DS loop detail; site serves 403 to plain fetchers — anti-bot caveat |
| https://d3no4ktch0fdq4.cloudfront.net/public/course/files/Meta_Full_Loop_Interview_Guide_-_Data_Scientist_Product_Analytics.pdf | interview_report | Meta's own candidate guide PDF; CDN URL may rot — mirror early |
| https://datalemur.com/ | interview_report | Question bank; partial paywall |
| https://netflixtechblog.com/interleaving-in-online-experiments-at-netflix-a04ee392ec55 | company_engineering_blog | Real experimentation practice at scale |
| https://medium.com/airbnb-engineering/beyond-a-b-test-speeding-up-airbnb-search-ranking-experimentation-through-interleaving-7087afa09c8e | company_engineering_blog | Airbnb experimentation methodology |
| https://365datascience.com/career-advice/career-guides/data-scientist-job-outlook-2025/ | role_taxonomy | Annual posting-derived skill percentages; URL-year drift |
| https://www.coursera.org/professional-certificates/google-advanced-data-analytics | role_taxonomy | Closest to a standard DS cert syllabus |
| https://www.datacamp.com/blog/data-scientist-interview-questions | interview_report | Canonical question set; refreshed yearly |

## Enrichment expectations

`python`, `machine learning`, `sql`, `statistics`, `a/b testing` should
dominate. `causal inference` and `bayesian statistics` may flag low —
keep; they are senior-differentiator vocabulary the corpus (entry-level
skewed) underrepresents. If `experiment design` flags zero while
`a/b testing` is high, that supports the fold-into-one-entry curation
call.

## Overlap with existing tracks

vs `mle`: the largest overlap of any pair (~20 shared entries); MLE keeps
serving/MLOps/distributed-training distinctives, DS keeps
inference/experimentation/product-sense distinctives. vs `swe`: shared
python/sql/git and light DS&A only. vs `data_analyst`: DS is the superset
on the modeling axis; DA is deeper on BI tooling and reporting ops
(https://roadmap.sh/ai-data-scientist/vs-data-analytics).
