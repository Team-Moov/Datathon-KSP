# CRIME — ML/AI pipeline

Synthetic-data crime analytics pipeline: co-offending network analysis, MO
linkage, risk scoring, lead recommendation, and sociological correlation.
Scope is ML/AI only — no frontend/backend/dashboard here. All data is
synthetic for now (see `data/synthetic.py`); real NCRB/NDAP integration is
deferred, `data/reference/` stays empty until that's picked up.

**To run everything: see `run_all.sh` or the command list at the bottom of
this file.** `pyrightconfig.json` fixes the "import not resolved" yellow
squiggles in VS Code/Pylance — those imports use runtime `sys.path`
manipulation (see "A note on imports" below), which static analysis can't
follow without being told where to look.

## What each file does

### `schema.sql`
The full Postgres schema: 15 tables, pgvector + pg_trgm extensions, all
indexes. Source of truth — includes tables added mid-build
(`person_graph_metric`, `district_composite_index`), so running this fresh
gets you everything, no separate migrations needed. `migrations/` still
holds the historical record of how it evolved, but isn't needed for setup.

### `load_data.py`
Loads the CSVs `data/synthetic.py` produces into Postgres, in FK-safe
order (districts → persons → incidents → offenses → roles → ...).

### `data/synthetic.py`
Generates the entire synthetic dataset: 31 real Karnataka districts (with
placeholder socio-economic figures — real ones are literal NCRB/NDAP rate
priors, see the file's docstring for exactly what's real vs. placeholder),
800 persons (20% flagged repeat-offenders), 1500 incidents/offenses spread
over 24 months, 130 ground-truth MO-linkage series (paraphrased, one fixed
"signature" per series), persistent co-offending "crews" (this is what
gives the network real community structure — without it, node2vec has
nothing to learn), and ~200 financial transactions with seeded
structuring/funnel-account patterns.

### `features/graph_utils.py`
**Shared** multiplex-graph builder — co-offending edges, MO-similarity
edges (from `mo_linkage_cluster`), financial edges. Single source of
truth; both `features/graph_features.py` and `models/lead_rec/` import
from here rather than each having their own copy (they used to — that was
a real bug, fixed). Supports `as_of_date` for temporal snapshots. Read the
leakage note in the docstring before including MO edges in a
historical/holdout graph.

### `features/graph_features.py`
Co-offending graph → Louvain communities + PageRank + betweenness
centrality. Writes to `person_graph_metric` (append-only, versioned).
PageRank and betweenness are computed differently on purpose — betweenness
needs edge weight inverted to a distance, PageRank doesn't; read the
docstring before touching this, it's a common subtle bug.

### `features/severity_history.py`
General-purpose CHI-weighted, recency-decayed offense-severity sum, "as of
any date." **Not currently wired into the risk-score model** — for a
person's first offense (which is what the current survival model's index
event is), prior history is always zero by construction, so it'd be a
useless constant feature there. It's the right building block if the
survival model is ever upgraded to recurrent events (3rd/4th offense
prediction). Standalone-useful as a dashboard figure regardless.

### `models/mo_linkage/train_siamese.py` + `infer.py`
TF-IDF + trained contrastive projection head (not a pretrained sentence-
transformer — this sandbox couldn't reach huggingface.co; upgrade path is
documented in the file) clustering offenses by MO signature. `train_*`
fits the model, tunes the clustering distance threshold on validation
data, saves artifacts. `infer.py` applies it to every offense and writes
to `mo_linkage_cluster`. Validated result: recall@3 79%→90% over a raw-
TF-IDF baseline; 90/130 true series recovered as one clean cluster.

### `models/lead_rec/train_node2vec_logreg.py` + `infer.py`
node2vec (unsupervised) + logistic regression on Hadamard-product pair
features, predicting new links. Validated via **temporal holdout**: train
on the graph as of 6 months before the data ends, check whether top
predictions match edges that actually appeared since — no synthetic label
needed, the graph's own edge-formation history is the ground truth.
`infer.py` scores 2-hop candidate pairs and writes `predicted_link` with a
human-readable evidence string (which edge types connect them). Validated
result: AUC ~0.77-0.81, precision@20 ~0.80 vs. 0.167 chance.

### `models/risk_score/train_survival.py` + `infer.py`
Random Survival Forest predicting time-to-second-offense with proper
right-censoring. Features: index-offense severity, PageRank centrality,
MO-cluster similarity, neighbor-average associate risk. `train_*` fits,
evaluates (concordance index vs. a severity-only baseline), tries SHAP
(genuinely fails on `RandomSurvivalForest` — falls back to permutation
importance, both outcomes reported honestly), saves the model. `infer.py`
scores everyone and writes `risk_score`. Validated result: concordance
0.71-0.75 vs. 0.50 baseline; **centrality dominates** — permutation
importance ~7x higher than severity_history, the empirical version of the
"network position matters more than raw offense count" thesis.

### `sociological/composite_index.py`
District socio-economic indicators → one composite score, via percentile-
ranking (default, matches the real NDAP-based India precedent) or PCA.
Writes to `district_composite_index` (versioned — separate from the
generator-baked `district_socioeconomic.composite_stress_index` column, so
this is independently re-runnable once real data replaces the
placeholder).

### `sociological/correlate.py`
Correlates the composite index against CHI-weighted crime severity vs.
raw incident counts, one statewide coefficient (deliberately not GWR —
cut from scope for hackathon-timeline stability, noted in the docstring).
Never joins to `Person`/`Case_Person_Role` — stays strictly district-level
to avoid the ecological fallacy. Currently returns a non-significant
correlation, honestly: the synthetic generator assigns district
essentially at random, with no deliberate socio-economic-crime
relationship baked in (unlike the crew structure for co-offending).

### `eval/survival_eval.py`, `eval/link_pred_holdout.py`
Evaluation logic factored out of the two training scripts (single source
of truth — both the training script and anything re-evaluating a saved
model later call the same functions). Not standalone CLI tools, just
shared building blocks.

### `eval/fairness_audit.py`
The non-negotiable check: does `risk_score` discriminate and calibrate
equally well across districts, and does the dominant feature (centrality)
correlate with district-level socio-economics in a way that would
reintroduce geography as a proxy for excluded protected attributes
(religion/caste were never modeled as features at all, anywhere in this
build). Validated result: clean separation (0 districts >0.10 below
overall concordance), some real calibration gaps worth knowing about
(Dharwad, Mysuru, Tumakuru rank mismatches), no significant proxy
correlation but underpowered at n=31 districts.

## A note on imports

Every script that needs a module from a sibling directory
(`features/graph_utils.py`, `eval/survival_eval.py`, etc.) does this at
the top:

```python
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[N] / "target_dir"))
from module_name import thing
```

`N` depends on how deep the calling file is — `eval/fairness_audit.py`
(1 level deep) uses `parents[1]`, `models/risk_score/train_survival.py`
(2 levels deep) uses `parents[2]`. This is runtime path manipulation, not
a real Python package — there's no `__init__.py`/`setup.py` anywhere, by
design, to keep this simple for a hackathon timeline. `pyrightconfig.json`
tells Pylance where to look so it stops flagging these as unresolved.

## Setup and run order

See `run_all.sh` for the full script. Summary:

```bash
# 1. System deps
apt-get update -qq && apt-get install -y postgresql postgresql-contrib postgresql-16-pgvector
service postgresql start

# 2. DB
su postgres -c "psql -c \"CREATE USER crimeportal WITH PASSWORD 'crimeportal' SUPERUSER;\""
su postgres -c "createdb -O crimeportal crimeportal"

# 3. Python deps
pip install --break-system-packages faker psycopg2-binary torch scikit-learn \
  scikit-survival shap node2vec gensim scipy joblib

# 4. Schema
PGPASSWORD=crimeportal psql -h localhost -U crimeportal -d crimeportal -f schema.sql

# 5. Data
cd data && python3 synthetic.py --out-dir ./output && cd ..
python3 load_data.py --data-dir ./data/output

# 6. Features
python3 features/graph_features.py
python3 features/severity_history.py

# 7. Models (train then infer, in this order — lead_rec and risk_score
#    both depend on mo_linkage's output; risk_score also depends on
#    graph_features' output)
cd models/mo_linkage && python3 train_siamese.py --out-dir ./artifacts && python3 infer.py --artifacts-dir ./artifacts && cd ../..
cd models/lead_rec && python3 train_node2vec_logreg.py --out-dir ./artifacts && python3 infer.py --artifacts-dir ./artifacts && cd ../..
cd models/risk_score && python3 train_survival.py --out-dir ./artifacts && python3 infer.py --artifacts-dir ./artifacts && cd ../..

# 8. Sociological
python3 sociological/composite_index.py
python3 sociological/correlate.py

# 9. Fairness audit (needs risk_score populated first)
cd eval && python3 fairness_audit.py --out-dir ./artifacts && cd ..
```

Re-running any `train_*.py` + `infer.py` pair adds new versioned rows —
nothing gets silently overwritten, per the append-only pattern used
throughout (`risk_score`, `predicted_link`, `mo_linkage_cluster`,
`person_graph_metric`, `district_composite_index`).