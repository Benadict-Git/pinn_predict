# AGENTS.md — PINN Groundwater Level Prediction

## Essential Commands (Run in Order)

**Phase 1 (run once, ~5 min):**
```bash
source .venv/bin/activate
python scripts/inspect_raw.py
python scripts/build_district_mapping.py
python scripts/build_station_table.py
python scripts/clean_rainfall.py
python scripts/clean_humidity.py
python scripts/clean_groundwater.py
python scripts/clean_well_stats.py
python scripts/build_recharge.py
python scripts/build_pumping.py
python scripts/merge_datasets.py   # produces observations.csv
python scripts/build_collocation_grid.py
python scripts/plot_sanity_checks.py
```

**CPU smoke test (verify plumbing, gradients):**
```bash
source .venv/bin/activate && python scripts/run_smoke_test.py
```
- Runs notebook with local patched directories, reduced epochs (`N_EPOCHS_ADAM=5`, `LBFGS_MAX_ITER=0`)
- Outputs discarded; use for integration checks only

## Critical Conventions an Agent Might Miss

**Data:**
- Station identification requires joining `(Station, canonical_district)` using `data/processed/district_name_mapping.csv`
- Phase 1 drops `|h| >= 200`; notebook clips to `H_MIN=-5`, `H_MAX=100`
- Telemetry sign is inverted (`-raw`) to match manual convention
- Never fabricate or silently synthesize missing data; scripts print counts dropped/filled

**Notebook:**
- Notebook paths are hardcoded to Kaggle (`/kaggle/input/datasets/benadictinfanta/water-data`, `/kaggle/working/`)
- **Do not edit notebook directly for local tests** — use `run_smoke_test.py` which patches paths
- Torch is only in virtual environment — activate `.venv` first
- No GPU available; real training requires Kaggle (T4/P100/L4)

**Evaluation (fixed since Run 12):**
- **Forecast (primary)**: known wells, `t >= cutoff` (~1.2‑yr horizon). Baseline: persistence (last known observation)
- **Spatial (secondary)**: held‑out wells (unknown locations). Baseline: kNN(x,y) on train well means (~11.6 m)
- Eval cell prints loud warning if model fails to beat **both** baselines
- Reported numbers are mean ± range over 3 seeds (except `SPLIT_SEED` which is pinned at 0)

**Settled Configuration (winning, Runs 36-38):**
- `USE_SEASONAL = True` — non-negotiable; disabling doubles forecast RMSE
- `W_PDE = 0.0` — PDE term ablated; no accuracy benefit over decoupled model
- `H0_ANCHOR_DAYS = 90` — 90-day rolling anchor (beats last-obs baseline 5.406m vs 5.500m)
- `USE_API = False` — causal antecedent precipitation adds variance, no accuracy gain
- `USE_ALPHA_SCALE = True` — learnable delta shrinkage via softplus(log_alpha)
- `N_EPOCHS_ADAM = 10000` — halved from 20000; data term flat from ~8,500 epochs

**Gotchas:**
- `SPLIT_SEED=0` is pinned — changing it invalidates baselines and comparisons with STATUS.md
- Learned `S`/`T` are unitless, relative cross‑district signals (not SI units)
- `LAPLACIAN_SCALE=1e10`, residual‑from‑anchor + dropout form, `W_DELTA=1e-2` are settled; do not tune them together with new features
- Dead ends: per‑well embeddings, h0‑anchor as non‑residual input, `CLAMP_T_TO_TRAIN`, `USE_TEMPORAL_WEIGHTS`

**Source of truth:**
- `STATUS.md` — read the tail first for latest run and "Next steps" before making changes