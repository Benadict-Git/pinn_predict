# CHAT.md – Project Summary for Pinpoint Groundwater Level Prediction

This file consolidates the key information from the project's markdown documentation.

## Files Integrated
- **AGENTS.md** – Overview of project phases, script order, and local environment.
- **CLAUDE.md** – Detailed project goal, data sources, modeling conventions, and current status.
- **STATUS.md** – Log of Phase 2 runs, checklist of completed steps, and known issues.
- **NEXT_STEPS_PLAN.md** – Planned next‑step experiments and actionable tasks.
- **DATA_DICTIONARY.md** – Description of all processed datasets and their schemas.

## High‑Level Summary
- **Goal**: Train a Physics‑Informed Neural Network (PINN) to predict groundwater depth `h(x, y, t)` across Tamil Nadu districts using the PDE \(S dh/dt = div(T grad(h)) + R - Q\).
- **Phases**:
  1. **Phase 1** – Data cleaning via a series of standalone Python scripts under `scripts/`. Outputs include `observations.csv`, `collocation.csv`, and supporting lookup tables.
  2. **Phase 2** – Training notebook `notebooks/pinn_train.ipynb`, executed on Kaggle/Colab (GPU). The notebook’s config cell controls all hyper‑parameters.
- **Key Data**:
  - Join key: `District LGD Code`.
  - Station identifier: `(Station, canonical_district)` (station names are not unique).
  - `R` is a unit‑less recharge proxy; `Q` is a static unit‑less pumping index.
- **Current Findings**:
  - Spatial task performance now exceeds the k‑NN baseline.
  - Forecast task still lags persistence; delta‑shrinkage analysis is planned.
  - `USE_SEASONAL` flag is provisional; `W_PDE` ablation will test physics contribution.

## Action Items (from NEXT_STEPS_PLAN.md)
1. Implement delta‑shrinkage sweep in the notebook eval cell.
2. Characterise forecast error tail with per‑well covariates.
3. Update stale comments about spatial ceiling.
4. Run `USE_SEASONAL=False` across three seeds to confirm its effect.
5. Ablate `W_PDE=0` across three seeds to evaluate the physics term.

## Where to Find Details
- **Scripts & Execution Order** – `AGENTS.md`.
- **Data Definitions & Limitations** – `DATA_DICTIONARY.md`.
- **Modeling Conventions & Hyper‑parameters** – `CLAUDE.md`.
- **Run Log & Known Issues** – `STATUS.md`.
- **Planned Experiments** – `NEXT_STEPS_PLAN.md`.

This consolidated view should help newcomers quickly understand the project's scope, data, model, and next steps.
