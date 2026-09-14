"""
Local training runner for PINN Groundwater Level Prediction.
Executes pinn_train.ipynb locally with:
  - Local dataset paths (data/processed/)
  - Elevation cache pre-seeded from kaggle/results/
  - Output artifacts saved to kaggle/results/{run_name}/
  - Configurable epochs, seeds, and feature flags
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_PATH = os.path.join(REPO_ROOT, "notebooks", "pinn_train.ipynb")
DATA_DIR_LOCAL = os.path.join(REPO_ROOT, "data", "processed")
ELEV_CACHE_SRC = os.path.join(REPO_ROOT, "kaggle", "results", "elevation_cache.csv")


def parse_args():
    parser = argparse.ArgumentParser(description="Local PINN Training Runner")
    parser.add_argument("--run-name", type=str, default="run34_local_alpha_rollanchor", help="Run name directory")
    parser.add_argument("--epochs", type=int, default=10000, help="Number of Adam training epochs")
    parser.add_argument("--seed", type=int, default=0, help="Optimization random seed")
    parser.add_argument("--split-seed", type=int, default=0, help="Benchmark split seed (pinned at 0)")
    parser.add_argument("--print-every", type=int, default=500, help="Logging frequency")
    parser.add_argument("--use-alpha-scale", type=str, default="True", choices=["True", "False"])
    parser.add_argument("--h0-anchor-days", type=int, default=90)
    parser.add_argument("--w-pde", type=float, default=1e-4)
    parser.add_argument("--use-api", type=str, default="True", choices=["True", "False"])
    parser.add_argument("--use-seasonal", type=str, default="True", choices=["True", "False"])
    return parser.parse_args()


class TeeLogger:
    """Tee stdout to both console and log file."""
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.logfile = open(filepath, "w", buffering=1)

    def write(self, message):
        self.terminal.write(message)
        self.logfile.write(message)

    def flush(self):
        self.terminal.flush()
        self.logfile.flush()

    def close(self):
        self.logfile.close()


def is_gpu_guard(src):
    return "compute_capability" in src and "subprocess" in src


def main():
    args = parse_args()
    out_dir = os.path.join(REPO_ROOT, "kaggle", "results", args.run_name)
    os.makedirs(out_dir, exist_ok=True)

    log_path = os.path.join(out_dir, "pinn-water-predict.log")
    tee = TeeLogger(log_path)
    sys.stdout = tee
    sys.stderr = tee

    print("=" * 70)
    print(f"PINN LOCAL TRAINING: {args.run_name}")
    print(f"Config: epochs={args.epochs}, seed={args.seed}, split_seed={args.split_seed}")
    print(f"Features: alpha_scale={args.use_alpha_scale}, h0_anchor_days={args.h0_anchor_days}, w_pde={args.w_pde}, api={args.use_api}")
    print(f"Output directory: {out_dir}")
    print("=" * 70)

    # Pre-seed elevation cache
    elev_dest = os.path.join(out_dir, "elevation_cache.csv")
    if os.path.exists(ELEV_CACHE_SRC):
        shutil.copy(ELEV_CACHE_SRC, elev_dest)
        print(f"[setup] Elevation cache seeded: {ELEV_CACHE_SRC} -> {elev_dest}")
    else:
        print(f"[setup] WARNING: {ELEV_CACHE_SRC} not found")

    with open(NB_PATH, "r") as f:
        nb = json.load(f)

    code_cells = [(i, "".join(c["source"]))
                  for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"]

    overrides = {
        'DATA_DIR = "/kaggle/input/datasets/benadictinfanta/water-data"':
            f'DATA_DIR = "{DATA_DIR_LOCAL}"',
        'OUTPUT_DIR = "/kaggle/working/"':
            f'OUTPUT_DIR = "{out_dir}/"',
        'N_EPOCHS_ADAM = 20000': f'N_EPOCHS_ADAM = {args.epochs}',
        'PRINT_EVERY = 500': f'PRINT_EVERY = {args.print_every}',
        'LBFGS_MAX_ITER = 500': 'LBFGS_MAX_ITER = 0',
        'RUN_LBFGS_FINETUNE = True': 'RUN_LBFGS_FINETUNE = False',
        'RUN_LBFGS_FINETUNE = False': 'RUN_LBFGS_FINETUNE = False',
        'USE_RAIN_ANOMALY = True': 'USE_RAIN_ANOMALY = False',
        'USE_VELOCITY = True': 'USE_VELOCITY = False',
        'USE_ALPHA_SCALE = True': f'USE_ALPHA_SCALE = {args.use_alpha_scale}',
        'H0_ANCHOR_DAYS = 90': f'H0_ANCHOR_DAYS = {args.h0_anchor_days}',
        'W_PDE = 0.0001': f'W_PDE = {args.w_pde}',
        'USE_API = True': f'USE_API = {args.use_api}',
        'USE_SEASONAL = True': f'USE_SEASONAL = {args.use_seasonal}',
    }

    def patch_src(src, cell_i):
        for old, new in overrides.items():
            src = src.replace(old, new)
        if cell_i == 4:
            src = re.sub(r"\bSEED\s*=\s*\d+", f"SEED = {args.seed}", src)
            src = re.sub(r"\bSPLIT_SEED\s*=\s*\d+", f"SPLIT_SEED = {args.split_seed}", src)
            src = re.sub(r"\bUSE_ALPHA_SCALE\s*=\s*\w+", f"USE_ALPHA_SCALE = {args.use_alpha_scale}", src)
            src = re.sub(r"\bH0_ANCHOR_DAYS\s*=\s*\d+", f"H0_ANCHOR_DAYS = {args.h0_anchor_days}", src)
            src = re.sub(r"\bW_PDE\s*=\s*[\w\.\d\-]+", f"W_PDE = {args.w_pde}", src)
            src = re.sub(r"\bUSE_API\s*=\s*\w+", f"USE_API = {args.use_api}", src)
            src = re.sub(r"\bUSE_SEASONAL\s*=\s*\w+", f"USE_SEASONAL = {args.use_seasonal}", src)
        return src

    ns = {"__name__": "__main__"}
    start_total = time.time()

    for cell_idx, raw_src in code_cells:
        src = patch_src(raw_src, cell_idx)

        if is_gpu_guard(src):
            print(f"[Cell {cell_idx:2d}] SKIP (GPU compat guard)")
            exec("import torch, numpy as np, pandas as pd, os, math", ns)
            continue

        preview = src.strip().replace("\n", " ")[:80]
        t0 = time.time()
        try:
            exec(compile(src, f"<cell {cell_idx}>", "exec"), ns)
            dt = time.time() - t0
            print(f"[Cell {cell_idx:2d}] OK ({dt:.1f}s) | {preview}")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"\n❌ [Cell {cell_idx:2d}] FAIL: {e}")
            print(tb)
            sys.exit(1)

    total_time = time.time() - start_total
    print("\n" + "=" * 70)
    print(f"✅ Training and evaluation finished in {total_time/60:.1f} minutes!")
    print(f"Outputs saved to {out_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
