"""
Phase 1 step 1: inspect every file in data/raw/ and print shape, dtypes,
columns, date ranges, missing-value counts, and unique station/district
counts. Run once per session before writing cleaning logic -- never assume
schema from memory.
"""
import os
import sys
import pandas as pd

RAW_DIR = "data/raw"

# Duplicate raw files confirmed byte-identical via `diff -q`; skip the "(1)"
# copies so every file is only inspected/cleaned once.
SKIP_FILES = {
    "pressure_tel_hr_tamil-nadu-sw-gw_tn_2021_2021(1).csv",
    "river_discharge_manual_daily_tamil_nadu_sw_gw_tn_2026_2030(1).csv",
}

DATE_COL_CANDIDATES = ["Data Acquisition Time"]


def inspect_file(path):
    fname = os.path.basename(path)
    size_mb = os.path.getsize(path) / 1e6
    print(f"\n{'=' * 90}")
    print(f"FILE: {fname}  ({size_mb:.2f} MB)")
    print("=" * 90)

    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as e:
        print(f"  FAILED TO READ: {e}")
        return

    print(f"  shape: {df.shape[0]} rows x {df.shape[1]} cols")
    print(f"  columns: {list(df.columns)}")
    print("  dtypes:")
    for col, dt in df.dtypes.items():
        print(f"    {col}: {dt}")

    print("  missing values per column (non-zero only):")
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if missing.empty:
        print("    none")
    else:
        for col, n in missing.items():
            pct = 100 * n / len(df) if len(df) else 0
            print(f"    {col}: {n} ({pct:.1f}%)")

    if "Station" in df.columns:
        print(f"  unique stations: {df['Station'].nunique()}")
    if "District" in df.columns:
        print(f"  unique districts: {df['District'].nunique()}")
        print(f"    district values: {sorted(df['District'].dropna().unique().tolist())}")

    date_col = next((c for c in DATE_COL_CANDIDATES if c in df.columns), None)
    if date_col:
        parsed = pd.to_datetime(df[date_col], format="%d-%m-%Y %H:%M", errors="coerce")
        n_bad = parsed.isna().sum() - df[date_col].isna().sum()
        print(f"  date column: '{date_col}'")
        print(f"    range: {parsed.min()} .. {parsed.max()}")
        if n_bad > 0:
            print(f"    WARNING: {n_bad} values failed to parse with format %d-%m-%Y %H:%M")

    if "Year" in df.columns:
        print(f"  Year range: {df['Year'].min()} .. {df['Year'].max()}")

    # Flag exact duplicate rows -- common in these telemetry exports.
    n_dupe = df.duplicated().sum()
    if n_dupe:
        print(f"  duplicate rows: {n_dupe}")


def main():
    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".csv"))
    print(f"Found {len(files)} CSV files in {RAW_DIR}/")
    skipped = [f for f in files if f in SKIP_FILES]
    if skipped:
        print(f"Skipping {len(skipped)} known duplicate file(s): {skipped}")

    for fname in files:
        if fname in SKIP_FILES:
            continue
        inspect_file(os.path.join(RAW_DIR, fname))


if __name__ == "__main__":
    main()
