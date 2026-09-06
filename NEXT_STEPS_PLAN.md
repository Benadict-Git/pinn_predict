# Plan — next steps after the Run 26-30 seed study

## Context

Thirty runs in, the state of the project is:

- **Spatial (secondary) is solved relative to its baseline.** `USE_TEMPORAL_WEIGHTS=False`
  (Runs 25-30) beats kNN in 3/3 seeds, mean 10.740m vs kNN 11.573m, with complete separation
  from the old weighted sampler. Adopted and settled.
- **Forecast (primary) has never beaten persistence** (5.500m) in thirty runs. Best single
  number ever recorded is 5.792m, and that is one seed.
- **The seed band is 0.505m on forecast RMSE.** Measured at fixed `SPLIT_SEED=0` (Runs 26-30).
  Every forecast difference logged in Runs 20-25 is smaller than this, so none of them are
  results. The project has been tuning inside its own noise for roughly ten runs.
- **The architecture ties persistence at initialisation** (5.48m, ~0 epochs) and gets *worse*
  with training. The learned deviation from the anchor is ~6m RMS — larger than the anchor's
  own test error.

That last point is the whole problem, and it has never been attacked directly. Everything so
far has added *features* to the delta. Nothing has asked the prior question: **is the learned
delta worth anything at all, at any magnitude?** That question is answerable almost for free,
and its answer determines whether the forecast task needs tuning or needs a different idea.

A second, unrelated liability: `USE_SEASONAL=True` is currently on in the notebook on the
strength of Run 22's unreplicated 0.34m — inside the 0.505m band. It is the only flag whose
"on" position rests on evidence the seed study has since invalidated.

### One idea checked and discarded during planning

STATUS.md Run 24 proposed rebuilding `h0` as a causal, horizon-matched anchor (last reading at
least H days before the row) to close the train/test anchor-quality gap (train 8.156m vs test
5.500m). **Measured on the population that now dominates the gradient — 2,028,247 rows from
2021+ on forecast wells — it makes things worse, not better:**

| anchor | error on those rows |
|---|---|
| current (last obs before cutoff) | **7.709m** |
| causal, H=90d | 8.141m |
| causal, H=193d (median forecast horizon) | 8.692m |
| causal, H=349d | 9.744m |

A lagged single reading carries a seasonal offset (H=193d is nearly anti-phase), while the
cutoff anchor behaves like a stable per-well level. **Do not implement the causal anchor as
specified in Run 24's next-steps.** That item should be struck.

## Approach

### Step 1 — Delta-shrinkage sweep in the eval cell (free, no training cost)

`forward()` returns `h0hat + mlp(...)`, so on the forecast set the prediction decomposes
exactly into anchor plus learned delta. Sweep a scalar on the delta *post hoc*:

```
h_alpha = h0 + alpha * (h_pred - h0)     for alpha in 0.0, 0.1, ..., 1.0
```

`alpha=0` is exactly persistence (5.500m); `alpha=1` is the current model. Report RMSE, MAE and
per-well win count at each. This costs one already-computed forward pass and answers the central
question directly:

- **interior minimum below 5.500m** → the delta has real signal that is simply mis-scaled, and
  the fix is a shrinkage constant, not another feature.
- **monotonically increasing** → the learned delta is net-harmful at every magnitude, and no
  amount of feature engineering on the current architecture will beat persistence. That is a
  publishable negative result and should redirect the project.

**Decided:** if the curve is monotonic, treat it as a real negative result — write it up in
STATUS.md, keep the spatial sampler win as the project's accuracy deliverable, and **stop
spending runs on forecast feature engineering** until there is a genuinely new idea. Steps 4-5
still run (they are about the evidence base and the physics claim, not about chasing the
forecast metric), but no further forecast features go in behind them.

File: `notebooks/pinn_train.ipynb` cell 26, immediately after the existing per-well diagnostic
(which already builds `fc_pred`, `pers_pred`, `fc_true` and the `fc_pw` per-well frame — reuse
them). The anchor per row is `fc["well_id"].map(persistence)`, already computed as
`fc_baselines["persistence (last obs before cutoff)"]`.

### Step 2 — Characterise the forecast tail (free, same cell)

Forecast RMSE 6.18m against a median per-well RMSE of 2.46m, with the worst-1% trim only
recovering to 4.72m, means the damage is spread across a broad tail rather than a few wells.
Extend the existing `pw` frame with per-well covariates already present in `train_df` — train
row count, `h` std within the train window, `|h0|`, district, and distance to the nearest train
well — and print the 20 worst wells plus the correlation of per-well PINN-minus-persistence
error with each covariate. This is the first look at *which* wells the model breaks, and it
costs nothing.

### Step 3 — Fix two stale claims in the notebook

`notebooks/pinn_train.ipynb` cell 26 still asserts the spatial task "is at its feature ceiling"
in a comment (line ~1602) and in the printed `note=` string (line ~1625). Runs 25-30 disproved
this. Correct both to reference the sampler finding.

### Step 4 — Replicate `USE_SEASONAL` at 3 seeds

Run `USE_SEASONAL=False` at `SEED=0,1,2`, `SPLIT_SEED=0`, uniform sampling, and compare means
and ranges against the existing 3-seed uniform+seasonal numbers (6.122 / 6.382 / 6.180). Three
runs, ~39 min. Whichever way it lands, one provisional flag becomes settled and CLAUDE.md's
"provisional" note gets replaced with a measurement.

### Step 5 — `W_PDE=0` ablation at 3 seeds (open since Run 17)

With `R`/`Q` as network inputs, the PDE term may contribute nothing to accuracy. Three runs.
The answer matters for how the project is described, not just tuned: if the physics term is
inert for accuracy, then `LAPLACIAN_SCALE`, `S` and `T` are a physics deliverable (learned
relative cross-district parameters) rather than an accuracy mechanism, and STATUS.md and
CLAUDE.md should say so plainly.

## Sequencing and cost

Steps 1-3 are one notebook edit and **one** confirmation run (~13 min) — do them together.
Step 1's result determines whether Steps 4-5 are worth their GPU time or whether the forecast
task needs a rethink first. Steps 4 and 5 are 3 runs each (~39 min each) and independent.

## Verification

- Steps 1-3: push v35 with the current adopted config (uniform, `SEED=0`, `SPLIT_SEED=0`,
  seasonal on) via the standard `kaggle kernels push` flow in the session scratchpad `push/`
  directory. Confirm forecast RMSE reproduces **6.122m** exactly — the run is deterministic, so
  any deviation means the eval edit changed the model path rather than only reporting, which is
  the specific bug class that cost a full run at v26.
- Confirm the alpha sweep prints `alpha=1.0` equal to the headline PINN RMSE and `alpha=0.0`
  equal to the persistence baseline, to three decimals. If either disagrees, the decomposition
  is wrong and nothing downstream should be believed.
- Steps 4-5: report mean + range over the 3 seeds per the protocol now in CLAUDE.md; a config
  that does not clear its own seed band has not been shown to do anything.
- Archive each run to `kaggle/results/runNN_<name>/` and log it in STATUS.md with config,
  both tasks' RMSE/MAE, and `S`/`T` behaviour, per the one-substantive-change-per-run rule.
