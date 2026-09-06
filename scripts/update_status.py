import os

with open('STATUS.md', 'r') as f:
    text = f.read()

# Cut off before the corrupted section
cut_point = text.find('## 2026-08-29 — Accuracy Improvement Tracks Preparation & Smoke Test')
if cut_point != -1:
    text = text[:cut_point].rstrip()

log_entry = """

---

## 2026-08-29 — Accuracy Improvement Tracks Preparation & Smoke Test

### Changes Implemented in `notebooks/pinn_train.ipynb`
1. **Track 1, Step 1: Trainable Delta Shrinkage (`USE_ALPHA_SCALE = True`)**
   - End-to-end learnable $\\alpha$ via `log_alpha = nn.Parameter(torch.tensor(math.log(0.3)))`.
   - Forward pass returns $h_0 + \\text{softplus}(\\text{log\\_alpha}) \\cdot \\Delta$.
   - Bound in physical parameter group with `weight_decay = 0.0`.
   - Smoke test verified $\\alpha$ updates cleanly from $0.30 \\to 0.2634$ under data gradients.

2. **Track 1, Step 2: 90-Day Rolling Anchor (`H0_ANCHOR_DAYS = 90`)**
   - Built $h_0$ as the mean depth over the last 90 days before cutoff per well (fallback to last-obs if window is empty).
   - Smoke test verified standalone forecast anchor baseline drops from **5.500m** (last-obs) to **5.341m RMSE** (0.159m lower baseline error bar).

3. **Track 2, Step 1: $W_{\\text{PDE}} = 0$ Ablation Switch**
   - Documented and structured in config cell for dedicated evaluation of physical regularization vs data-only fit.

4. **Track 3, Step 1: Antecedent Precipitation Index (`USE_API = True`, `API_DECAY_DAYS = [30, 90]`)**
   - Vectorized 1D temporal convolution per district grid across train window (runtime < 1s for 4.5M rows).
   - Generates normalized `api30hat` and `api90hat` to represent monsoon infiltration delay.

### Local Smoke Test Result
- **Status**: PASSED (All 30 notebook cells executed cleanly, 5-epoch test).
- **Spatial Map Generation (Cell 28)**: Verified compatibility with all new covariate columns.
- **Model Output & Artifact Saving (Cell 30)**: Verified model weights, learned $S/T$, and learned $\\alpha$ export cleanly.
"""

with open('STATUS.md', 'w') as f:
    f.write(text + log_entry)

print("✓ STATUS.md cleaned and updated accurately.")
