"""
Smoke-test harness for pinn_train.ipynb.
Executes every code cell in one shared namespace with:
  - DATA_DIR / OUTPUT_DIR patched to local paths
  - elevation cache seeded from kaggle/results/ BEFORE the elevation cell runs
  - N_EPOCHS_ADAM=5, LBFGS_MAX_ITER=0 (plumbing only, no real training)
  - USE_RAIN_ANOMALY=False, USE_VELOCITY=False, RUN_LBFGS_FINETUNE=False

Run from repo root:
  source .venv/bin/activate && python scripts/run_smoke_test.py
"""
import json, sys, os, shutil, traceback

NB_PATH = "notebooks/pinn_train.ipynb"
DATA_DIR_LOCAL = "data/processed"
OUTPUT_DIR_LOCAL = "/tmp/pinn_smoke_out"
ELEV_CACHE_SRC = "kaggle/results/elevation_cache.csv"

os.makedirs(OUTPUT_DIR_LOCAL, exist_ok=True)

# Pre-seed the elevation cache so the API call is never needed
elev_dest = os.path.join(OUTPUT_DIR_LOCAL, "elevation_cache.csv")
if os.path.exists(ELEV_CACHE_SRC):
    shutil.copy(ELEV_CACHE_SRC, elev_dest)
    print(f"[setup] Elevation cache seeded: {ELEV_CACHE_SRC} -> {elev_dest}")
else:
    print(f"[setup] WARNING: {ELEV_CACHE_SRC} not found — elevation cell will try the network")

with open(NB_PATH) as f:
    nb = json.load(f)

code_cells = [(i, "".join(c["source"]))
              for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"]

# String-level overrides applied to every cell source before exec
OVERRIDES = {
    'DATA_DIR = "/kaggle/input/datasets/benadictinfanta/water-data"':
        f'DATA_DIR = "{DATA_DIR_LOCAL}"',
    'OUTPUT_DIR = "/kaggle/working/"':
        f'OUTPUT_DIR = "{OUTPUT_DIR_LOCAL}/"',
    'N_EPOCHS_ADAM = 20000': 'N_EPOCHS_ADAM = 5',
    'LBFGS_MAX_ITER = 500':  'LBFGS_MAX_ITER = 0',
    'USE_RAIN_ANOMALY = True':  'USE_RAIN_ANOMALY = False',
    'USE_VELOCITY = True':       'USE_VELOCITY = False',
    'RUN_LBFGS_FINETUNE = True': 'RUN_LBFGS_FINETUNE = False',
    'RUN_LBFGS_FINETUNE = False': 'RUN_LBFGS_FINETUNE = False',  # keep it off
}


def patch(src):
    for old, new in OVERRIDES.items():
        src = src.replace(old, new)
    return src


def is_gpu_guard(src):
    """Skip the GPU/torch compat guard cell (subprocess + compute_capability probe)."""
    return "compute_capability" in src and "subprocess" in src


ns = {"__name__": "__main__"}

print("=" * 60)
print("PINN Smoke Test — verifying Steps 1-4 plumbing (5 epochs)")
print("=" * 60)

errors = []
for cell_idx, raw_src in code_cells:
    src = patch(raw_src)

    if is_gpu_guard(src):
        print(f"[Cell {cell_idx:2d}] SKIP (GPU compat guard)")
        exec("import torch, numpy as np, pandas as pd, os, math", ns)
        continue

    preview = src.strip().replace("\n", " ")[:80]
    try:
        exec(compile(src, f"<cell {cell_idx}>", "exec"), ns)
        print(f"[Cell {cell_idx:2d}] OK  | {preview}")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Cell {cell_idx:2d}] FAIL| {preview}")
        print(f"         ERROR: {e}")
        errors.append((cell_idx, str(e), tb))
        print("\nFull traceback:")
        print(tb)
        break

print()
if errors:
    print(f"❌ Smoke test FAILED at cell {errors[0][0]}: {errors[0][1]}")
    sys.exit(1)
else:
    print("✅ Smoke test PASSED — all cells executed without error")
    for k in ["fc_rmse", "sp_rmse", "fc_mae"]:
        if k in ns:
            print(f"  {k} = {ns[k]:.3f}m  (5-epoch, meaningless for accuracy)")
    # Report Step 1: learned alpha
    model = ns.get("model")
    if model is not None and hasattr(model, "log_alpha") and model.log_alpha is not None:
        import torch.nn.functional as F_
        a = float(F_.softplus(model.log_alpha).item())
        print(f"  Step 1 — learned alpha = {a:.4f} (init ~0.30)")
    # Report Step 2: anchor RMSE printed by preprocessing
    print("\nKey diagnostics are in stdout above (Step 2 anchor RMSE, Step 4 API coverage).")
    print("Next: push the patched notebook to Kaggle for a real 20k-epoch run.")
