# PINN Groundwater Level Prediction — Tamil Nadu

## Project goal

Build a Physics-Informed Neural Network (PINN) to predict groundwater level
`h(x, y, t)` across Tamil Nadu districts. Governing physics is the 2D
transient unconfined groundwater flow equation:

```
S(x,y) * dh/dt = div(T(x,y) * grad(h)) + R(x,y,t) - Q(x,y,t)
```

- `S` = storage coefficient (unknown, learned per district — inverse problem)
- `T` = transmissivity (unknown, learned per district — inverse problem)
- `R` = recharge forcing, from rainfall / soil moisture / humidity / temperature
- `Q` = pumping/extraction sink, approximated from well/irrigation statistics

**Current phase: Phase 2 — iterating on Kaggle training runs.** Phase 1 (data
cleaning) is complete and its outputs are frozen. `STATUS.md` is the source of
truth for run-by-run progress; read its tail ("Next steps") before changing
anything in the notebook.

## Directory structure

- `data/raw/` — original downloaded files, untouched. Inspect via scripts,
  never read wholesale into context (see `.claudeignore`).
- `data/processed/` — cleaned outputs: `observations.csv` (368MB, 4.58M rows),
  `collocation.csv`, `district_name_mapping.csv`, `DATA_DICTIONARY.md`,
  `plots/`.
- `scripts/` — standalone Python scripts, one responsibility each. Phase 1
  lives here.
- `notebooks/pinn_train.ipynb` — Phase 2: a single self-contained training
  notebook, authored here but run externally (Kaggle/Colab).
- `kaggle/results/` — per-run artifacts pulled back from Kaggle (weights,
  learned `S`/`T`, plots, run log, elevation cache).
- `.venv/` — local venv with pandas/numpy/matplotlib **and torch 2.13.0+cpu**.

## Commands

Phase 1 scripts run from the repo root, hardcoded paths, no CLI args, in order:

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

A full Phase 1 re-run takes ~5 minutes and ~2GB RAM. Scripts log what they
drop and why via `print()`.

## Local execution policy

- **No GPU on this machine.** Real training happens on Kaggle (T4/P100/L4).
- CPU **smoke tests** of the notebook (2–30 epochs, outputs discarded) are
  expected and encouraged — they catch plumbing/gradient bugs cheaply and have
  caught real ones. Always cut `N_EPOCHS_ADAM` and `LBFGS_MAX_ITER` to single
  digits first.
- A full-length local CPU run is ~30–60 min; acceptable for a controlled
  ablation, but Kaggle is the system of record for reported numbers.
- Notebook paths are hardcoded to Kaggle
  (`/kaggle/input/datasets/benadictinfanta/water-data`, `/kaggle/working/`) —
  these are permanent settings, not placeholders. Local runs patch them in a
  scratch harness rather than editing the notebook.
- Kaggle CLI push: `dataset_sources` must be `benadictinfanta/water-data`
  (no `datasets/` prefix). Kaggle sometimes allocates a Tesla P100 (cc 6.0),
  which the bundled torch does not support — the notebook's first cell is a
  GPU/torch compatibility guard that installs `torch==2.5.1+cu118` only when
  compute capability < 7. Settings > Internet must be **on** (SRTM elevation
  API lookup).

## Data sources (see STATUS.md for the full per-file inventory)

All NWIC/NWDP files share a common schema: `SlNo, Station, Agency, State LGD
Code, State, District LGD Code, District, Tehsil, Block, Village, River,
Basin, ..., Latitude, Longitude, Data Acquisition Time, <measurement>`.
`District LGD Code` is the canonical join key across NWIC files — it is
stable across the 2019-2020 Tamil Nadu district reorganization and across
spelling variants (e.g. "Tiruvannamalai" vs "Thiruvannamalai" both carry
LGD code 593); district *names* differ across sources and eras and are not
safe to join on directly.

| Source file(s) | Provides | Feeds |
|---|---|---|
| `gwl_manual_quarterly_*` (1950-1990, 1991-2020) | Quarterly manual groundwater depth readings, ~2500 stations | `h` observations |
| `gwl_tel_6_hourly_*` (1991-2020, 2021-2025, 2026-2030) | 6-hourly telemetry groundwater depth, up to 849 stations | `h` observations |
| `RS_Session_257_AU_896_3.csv` | Rajya Sabha district-year depth-bin histograms (2019-2021), 33 districts | cross-validation for `h` (aggregated, not point data) |
| `rainfall_tel_hr_*` (2021-2025, 2026-2030) | Hourly telemetry rainfall, ~145 stations, 36 districts | `R` |
| `rainfall_manual_daily_tn_1991_2020` / `_1961_1990` | Daily manual rainfall, sparse (9 districts / 1 district) | `R` (limited historical coverage) |
| `humid_tel*_hr_*` (2021-2026) | Hourly relative humidity, 45 stations, 26 districts | `R` (ET proxy) |
| `pressure_tel_hr_*` (2021-2026) | Hourly atmospheric pressure, 45 stations, 26 districts | supplementary only — not required by the PDE, not currently used |
| `area_irrigated_by_wells_by_districts_in_tn_2018_19.csv` | District-level irrigated area by well type, 2018-19 snapshot | `Q` |
| `number_source_of_irrigation_through_wells_tn_2018_19.csv` | District-level well counts by type/power source, 2018-19 snapshot | `Q` |
| `classification_of_usage_of_wells_for_domestic_and_industrial_purposes_by_districts_in_tn_2018_19.csv` | District-level domestic/industrial well usage counts, 2018-19 snapshot | `Q` |

**Not used in the pipeline** (present in `data/raw/` but out of scope for the
PDE terms `S, T, R, Q, h`): `rwl_*` (river water level), `river_discharge_*`
(both files are empty — header only, 0 data rows). Documented in STATUS.md,
not deleted.

**Absent from `data/raw/` despite being listed as a candidate source**: no
temperature file, no ERA5-Land extract, no DEM. Recharge proxy `R` is built
without true Hargreaves ET (which needs Tmax/Tmin) — see STATUS.md for the
adapted formula and `scripts/build_recharge.py` for the implementation. If
either becomes available later, re-run `build_recharge.py` and note the
improvement in STATUS.md rather than reworking the formula silently.
Elevation is fetched at notebook runtime from the Open Topo Data SRTM API and
cached (`elevation_cache.csv`).

## Data facts that matter for any change here

- **Join key**: `District LGD Code`. District *names* must go through
  `data/processed/district_name_mapping.csv`.
- **Station is not unique**: 181 station names repeat across unrelated
  districts. Always key on `(Station, canonical_district)`.
- **Telemetry sign was inferred**, not confirmed: telemetry `h` was flipped
  (`-raw`) to match the manual convention (STATUS.md issue 1).
- **Sentinel filter**: Phase 1 drops `|h| >= 200`; the notebook additionally
  clips to `H_MIN=-5, H_MAX=100` (a modeling choice, in the config cell).
- **`R` is a unitless proxy**, NaN for ~80% of observation rows (zero coverage
  before 2021; only 26 of 38 districts have humidity). Collocation rows get a
  rainfall-only and then a state-monthly-mean fallback; observation rows are
  filled with the mean.
- **`Q` is a unitless [0,1] index** from a single 2018-19 snapshot — static,
  not time-varying.
- **`R`/`Q` are not in SI units**, so learned `T`/`S` are *relative*
  cross-district signals, never m²/day or true storage coefficients
  (DATA_DICTIONARY.md limitation 4).
- **19.5% of manual groundwater rows have `Station="#REF!"`** (Excel artifact).
  Dropped, not reassigned.

## Modeling conventions (Phase 2)

- The network predicts **normalized depth `h`**, not head. Head is
  99.9% explained by elevation, which is already an input, so a head target
  made the loss nearly indifferent to depth error (STATUS.md, Run 11).
- **Residual-from-anchor form**: `forward()` returns `h0hat + mlp(...)` — the
  model starts at persistence and learns only a deviation. `H0_DROPOUT_P`
  zeroes the anchor on a fraction of training rows so unanchored inputs
  (held-out wells, collocation) stay in-distribution.
- `S_raw`/`T_raw` are physical inverse-problem parameters and are excluded
  from weight decay (their own optimizer param group).
- `LAPLACIAN_SCALE` multiplies only the diffusion term's contribution to the
  residual — without it `T` gets no visible gradient at Tamil Nadu's spatial
  scale.
- **Dead ends — do not revive**: per-well embeddings (Run 18) and the
  h0-anchor as a non-residual input (Run 19).
- **Settled, do not tune alongside a new feature**: `W_PDE=1e-4`,
  `LAPLACIAN_SCALE=1e10`, `H0_DROPOUT_P=0.3`, `W_DELTA=1e-2`.
- **`USE_TEMPORAL_WEIGHTS=False`** (Runs 25-30). Year-equalizing batch weights
  gave the 2021+ telemetry era 7.5% of the gradient despite being 69% of the
  training rows and 100% of the evaluation population. Uniform sampling is worth
  ~0.88m on the spatial task with complete separation across 3 seeds, and makes
  no measurable forecast difference.
- **`USE_SEASONAL=True` is provisional**, not settled — it rests on Run 22's
  single-run 0.34m gain, which is inside the 0.505m seed band. Re-test at 3
  seeds before building on it.
- **`CLAMP_T_TO_TRAIN`**: tested (Run 23), no measurable effect. Do not revive
  without a new mechanism.

## Evaluation protocol (fixed since Run 12)

Two tasks, both reported every run:

- **Forecast (primary)**: known wells, `t >= TEMPORAL_CUTOFF_QUANTILE`
  (~1.2-year horizon). Baseline to beat: **persistence** (last obs before the
  cutoff, 5.50m RMSE), not the district mean.
- **Spatial (secondary)**: held-out wells, all `t`. Baseline to beat:
  **kNN(x,y)** on train well means (~11.57m), not the district mean (12.07m —
  too weak a bar, and it hid the real ceiling for eleven runs).

The eval cell prints a loud warning if the model fails to beat both. Never
report a number against the district-mean baseline alone.

**Every config is run at 3 seeds and reported as mean + range** (Runs 26-30).
Training is fully deterministic, so repeating a config is worthless — but the
optimisation trajectory is chaotically sensitive, and the measured seed band is
**0.505m on forecast RMSE** and **0.337-0.854m on spatial RMSE**. A single-run
difference smaller than that is not a result. ~39 min per config on a P100.

- `SEED` perturbs weight init and batch draws only.
- **`SPLIT_SEED` is pinned at 0** — it draws the held-out wells, and every run
  from 7 on was scored against that draw. Changing it silently moves every
  baseline (at `SPLIT_SEED=1`: persistence 5.500 → 5.686, kNN 11.573 → 9.861)
  and invalidates comparison with the whole of STATUS.md.
- The spatial task is **not** at a feature ceiling. That claim stood from Run 12
  to Run 25 and was a sampler artifact; with uniform sampling the PINN beats kNN
  in 3/3 seeds. Do not repeat it.

## Coding conventions

- Concise, direct code. Plain `print()` statements for logging — no logging
  framework.
- No unnecessary abstraction. Phase 1 is standalone scripts under `scripts/`,
  each with one responsibility, run in sequence.
- Phase 2 is a single self-contained notebook, not scripts. Its config cell is
  the single entry point for every hyperparameter.
- Comments in the notebook carry the *why* and the tuning history for each
  choice; keep that convention when changing a value.
- Never fabricate or silently synthesize missing data. Always print what was
  dropped/filled and why, and reflect it in STATUS.md / DATA_DICTIONARY.md.
- **One substantive change per training run.** Runs are logged in STATUS.md
  with config, RMSE/MAE on both tasks, and `S`/`T` behavior; a run that
  changes several things at once is uninterpretable. New features are added
  behind config flags so they can be ablated one at a time.

## Current status

See STATUS.md — read the tail first (latest run + "Next steps").
