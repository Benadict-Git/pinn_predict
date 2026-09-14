"""
Harness to configure, stage, push, monitor, and retrieve Kaggle runs for the PINN model.
Usage:
    python scripts/run_seed_battery.py --run-name run34_alpha_rollanchor_api --seeds 0
    python scripts/run_seed_battery.py --run-name run35_wpde0_ablation --w-pde 0.0 --seeds 0 1 2
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_PATH = os.path.join(REPO_ROOT, "notebooks", "pinn_train.ipynb")
KERNEL_SLUG = "benadictinfanta/pinn-water-predict"
DEFAULT_PUSH_DIR = os.path.join(REPO_ROOT, "kaggle", "push_staging")


def parse_args():
    parser = argparse.ArgumentParser(description="PINN Kaggle Seed Battery Runner")
    parser.add_argument("--run-name", type=str, required=True, help="Run prefix name (e.g. run34_alpha_rollanchor)")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0], help="Seed(s) to run (e.g. 0 1 2)")
    parser.add_argument("--use-alpha-scale", type=str, default=None, choices=["True", "False"])
    parser.add_argument("--h0-anchor-days", type=int, default=None)
    parser.add_argument("--w-pde", type=float, default=None)
    parser.add_argument("--use-api", type=str, default=None, choices=["True", "False"])
    parser.add_argument("--use-seasonal", type=str, default=None, choices=["True", "False"])
    parser.add_argument("--n-epochs-adam", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Stage files and verify without pushing to Kaggle")
    parser.add_argument("--poll-interval", type=int, default=30, help="Status polling interval in seconds")
    return parser.parse_args()


def prepare_notebook_source(seed, overrides):
    with open(NB_PATH, "r") as f:
        nb = json.load(f)

    # Find Cell 4 (config cell)
    cfg_src = "".join(nb["cells"][4]["source"])

    # Update SEED
    cfg_src = re.sub(r"\bSEED\s*=\s*\d+", f"SEED = {seed}", cfg_src)

    # Update optional flag overrides
    for k, v in overrides.items():
        if v is not None:
            pattern = rf"\b{k}\s*=\s*[\w\.\d\-]+"
            if re.search(pattern, cfg_src):
                cfg_src = re.sub(pattern, f"{k} = {v}", cfg_src)
            else:
                print(f"[warning] Parameter {k} not found in config cell regex.")

    nb["cells"][4]["source"] = [line + "\n" for line in cfg_src.rstrip("\n").split("\n")]
    if nb["cells"][4]["source"]:
        nb["cells"][4]["source"][-1] = nb["cells"][4]["source"][-1].rstrip("\n")

    return nb


def stage_kernel(push_dir, nb_dict):
    os.makedirs(push_dir, exist_ok=True)
    nb_file = os.path.join(push_dir, "pinn_train.ipynb")
    with open(nb_file, "w") as f:
        json.dump(nb_dict, f, indent=1)

    meta = {
        "id": KERNEL_SLUG,
        "title": "pinn-water-predict",
        "code_file": "pinn_train.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": True,
        "keywords": ["gpu"],
        "dataset_sources": ["benadictinfanta/water-data"],
        "kernel_sources": [],
        "competition_sources": [],
        "model_sources": []
    }
    meta_file = os.path.join(push_dir, "kernel-metadata.json")
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)

    return push_dir


def push_to_kaggle(push_dir):
    print(f"--> Pushing {KERNEL_SLUG} to Kaggle...")
    cmd = ["kaggle", "kernels", "push", "-p", push_dir]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Error pushing to Kaggle:\n{res.stderr}")
        return False
    print(res.stdout.strip())
    return True


def wait_for_completion(poll_interval=30):
    print(f"--> Monitoring Kaggle kernel execution...")
    start_t = time.time()
    while True:
        res = subprocess.run(["kaggle", "kernels", "status", KERNEL_SLUG], capture_output=True, text=True)
        out = res.stdout.strip()
        elapsed = int(time.time() - start_t)
        print(f"  [{elapsed}s] {out}")

        if "COMPLETE" in out:
            print("✅ Kernel execution finished successfully!")
            return True
        elif "ERROR" in out or "CANCELLED" in out:
            print(f"❌ Kernel run stopped with status: {out}")
            return False

        time.sleep(poll_interval)


def pull_results(target_dir):
    os.makedirs(target_dir, exist_ok=True)
    print(f"--> Pulling artifacts to {target_dir}...")
    res = subprocess.run(["kaggle", "kernels", "output", KERNEL_SLUG, "-p", target_dir], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Error pulling output:\n{res.stderr}")
        return False
    print(res.stdout.strip())
    return True


def extract_metrics(log_path):
    if not os.path.exists(log_path):
        return {}
    with open(log_path, "r") as f:
        content = f.read()

    metrics = {}
    # Forecast RMSE
    fc_m = re.search(r"PINN\s+([\d\.]+)\s+([\d\.]+)", content)
    if fc_m:
        metrics["fc_rmse"] = float(fc_m.group(1))
        metrics["fc_mae"] = float(fc_m.group(2))

    # Spatial RMSE
    sp_m = re.search(r"=== SPATIAL.*?PINN\s+([\d\.]+)\s+([\d\.]+)", content, re.DOTALL)
    if sp_m:
        metrics["sp_rmse"] = float(sp_m.group(1))
        metrics["sp_mae"] = float(sp_m.group(2))

    # Learned alpha
    alpha_m = re.search(r"Learned delta scale alpha\s*=\s*([\d\.]+)", content)
    if alpha_m:
        metrics["alpha"] = float(alpha_m.group(1))

    return metrics


def main():
    args = parse_args()
    overrides = {
        "USE_ALPHA_SCALE": args.use_alpha_scale,
        "H0_ANCHOR_DAYS": args.h0_anchor_days,
        "W_PDE": args.w_pde,
        "USE_API": args.use_api,
        "USE_SEASONAL": args.use_seasonal,
        "N_EPOCHS_ADAM": args.n_epochs_adam,
    }

    results = []
    for seed in args.seeds:
        run_id = f"{args.run_name}_seed{seed}"
        out_dir = os.path.join(REPO_ROOT, "kaggle", "results", run_id)
        print("\n" + "=" * 70)
        print(f"RUNNING: {run_id} (SEED = {seed})")
        print("=" * 70)

        nb_dict = prepare_notebook_source(seed, overrides)
        stage_dir = stage_kernel(DEFAULT_PUSH_DIR, nb_dict)

        if args.dry_run:
            print(f"[dry-run] Staged to {stage_dir}. Skipping push.")
            continue

        success = push_to_kaggle(stage_dir)
        if not success:
            print(f"Aborting battery due to push failure at seed {seed}.")
            break

        completed = wait_for_completion(poll_interval=args.poll_interval)
        if not completed:
            print(f"Aborting battery due to kernel failure at seed {seed}.")
            break

        pull_results(out_dir)
        log_file = os.path.join(out_dir, "pinn-water-predict.log")
        m = extract_metrics(log_file)
        m["seed"] = seed
        results.append(m)
        print(f"Metrics for seed {seed}: {m}")

    if results:
        print("\n" + "=" * 70)
        print(f"BATTERY RESULTS: {args.run_name}")
        print("=" * 70)
        for r in results:
            print(r)


if __name__ == "__main__":
    main()
