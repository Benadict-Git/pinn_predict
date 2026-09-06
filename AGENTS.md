# AGENTS.md — PINN Groundwater Level Prediction

## Project structure

Two phases. Phase 1 scripts are one-shot data-cleaning; Phase 2 is a single notebook for Kaggle/Colab.

```
scripts/              # Phase 1 — standalone .py, one responsibility each
notebooks/pinn_train.ipynb  # Phase 2 — self-contained, runs on Kaggle T4/Colab
data/raw/             # untouched originals (in .claudeignore — never read raw)
data/processed/       # cleaned outputs (observations.csv: 368MB, 4.6M rows)
kaggle/results/       # per-run artifacts (model weights, plots, learned params)
```

## Commands

All Phase 1 scripts run from the repo root with hardcoded paths — no CLI args. Run them in order:

```bash
source .venv/bin/activate

python scripts/inspect_raw.py
python scripts/build_district_mapping.py
python scripts/build_station_table.py
python scripts/clean_rainfall.py
python scripts/clean_humidity.py
python scripts/clean_groundwater.py        # ~2min, 4.6M rows
python scripts/clean_well_stats.py
python scripts/build_recharge.py
python scripts/build_pumping.py
python scripts/merge_datasets.py           # produces 368MB observations.csv
python scripts/build_collocation_grid.py
python scripts/plot_sanity_checks.py
```

A full Phase 1 re-run takes ~5 minutes and ~2GB RAM. The scripts log what they drop and why via `print()`.

### Testing

Run a CPU smoke test of the notebook (5 epochs, outputs discarded) to verify plumbing and gradients:

```bash
source .venv/bin/activate && python scripts/run_smoke_test.py
```

This executes every notebook cell with:
- Local data/output directories patched
- Elevation cache pre-seeded from kaggle/results/
- Reduced epochs: `N_EPOCHS_ADAM=5`, `LBFGS_MAX_ITER=0`
- Feature flags disabled: `USE_RAIN_ANOMALY=False`, `USE_VELOCITY=False`, `RUN_LBFGS_FINETUNE=False`

## Local environment

- `.venv` has pandas, numpy, matplotlib, **and torch 2.13.0+cpu** (contradicts what CLAUDE.md says — ignore that note).
- **No GPU.** CPU smoke tests (2–30 epochs) are fine for catching integration bugs and verifying gradients. Real training would waste hours here.
- `torch` is not in the base (system) Python — activate the venv first.

## The notebook (`notebooks/pinn_train.ipynb`)

- **Authored locally, run on Kaggle/Colab.** Do not run it locally for real training. CPU smoke tests at 2–30 epochs are acceptable for plumbing checks, always with `N_EPOCHS_ADAM` and `LBFGS_MAX_ITER` cut to single digits, and outputs discarded.
- Paths are hardcoded to Kaggle (`/kaggle/input/datasets/benadictinfanta/water-data`, `/kaggle/working/`) — no placeholders.
- Requires Kaggle Settings > Internet **on** (SRTM elevation API lookup).
- The config cell is the single entry point for all hyperparameters (`W_PDE`, `LAPLACIAN_SCALE`, `HIDDEN_WIDTH`, `WEIGHT_DECAY`, `TEMPORAL_CUTOFF_QUANTILE`, etc.).

## Architecture

- **Phase 1 → Phase 2 pipeline**: Scripts clean raw data → produce `observations.csv` → notebook trains PINN on this data
- **Station identification**: Not unique by name; must use `(Station, canonical_district)` via `data/processed/district_name_mapping.csv`
- **PINN architecture**: Predicts normalized depth `h`; uses residual-from-anchor form (`h0hat + mlp(...)`); learns `S`/`T` per district as inverse problem parameters
- **Data flow**: Raw CSV files → cleaned CSVs → merged `observations.csv` → notebook tensors → PINN forward pass → PDE residual loss + data loss

## Conventions

- **Logging**: Plain `print()` statements — no logging framework (see any script, e.g. `scripts/clean_groundwater.py:73-75`)
- **Constants**: Defined at top of files in UPPER_CASE (see `SENTINEL_ABS_THRESHOLD = 200` in `clean_groundwater.py:45`)
- **Merging**: Always join on `(Station, canonical_district)` after mapping district names via `district_name_mapping.csv`
- **Error handling**: Check for missing data, print counts dropped, continue processing (see sentinel handling in `clean_groundwater.py:66-67`)
- **Notebook**: Config cell is single source of truth for hyperparameters; comments document *why* and tuning history
- **No unnecessary abstraction**: Phase 1 = standalone single-responsibility scripts under `scripts/`; Phase 2 = single self-contained notebook
- **Data integrity**: Never fabricate or silently synthesize missing data; always print what was dropped/filled and why
- **Experimental discipline**: One substantive change per training run; new features added behind config flags for ablation

## Gotchas

- **SPLIT_SEED=0 is pinned**: Changing it invalidates baselines and comparisons with STATUS.md (see CLAUDE.md:191-194)
- **Spatial task baseline**: Beats kNN(x,y) (~11.6m), not district mean (12.07m — too weak)
- **Telemetry sign**: Inferred convention (flipped to match manual); unconfirmed — see STATUS.md issue 1
- **Sentinel filtering**: Phase 1 drops `|h| >= 200`; notebook clips to `H_MIN=-5, H_MAX=100`
- **R/Q units**: Unitless proxies; learned `T`/`S` are relative cross-district signals, not SI units
- **Station="#REF!"**: 19.5% of manual rows have this Excel artifact; dropped, not reassigned
- **CPU vs Kaggle**: Local smoke tests acceptable for plumbing; real training requires Kaggle (T4/P100/L4); local full runs waste hours
- **Notebook paths**: Hardcoded to Kaggle; never edit directly — use scratch harness like `run_smoke_test.py` for local patches
- **One change per run**: STATUS.md logs each run; changing multiple configs at once makes results uninterpretable
- **GPU compatibility**: Notebook first cell guards against incompatible torch/CUDA versions on Kaggle

## Evaluation (from Run 12 onward)

Dual evaluation, both reported every run:
- **Forecast** (primary): known wells, `t >= cutoff` (~1.2yr horizon). Baseline: **persistence** (last known obs), not the district mean.
- **Spatial** (secondary): held-out wells (unknown locations). Baseline: **kNN**(x,y) on train well means (~11.6m), not the district mean (12.07m — too weak).

The eval cell prints a loud warning ("PINN LOSES to the best baseline") if the model fails to beat both.

## STATUS.md is the source of truth

Every Phase 2 run is logged there with RMSE/MAE, config values, spatial map quality, and `S`/`T` behavior. Read the tail first — it has the most recent run and the "Next steps" list that defines what should come next.
