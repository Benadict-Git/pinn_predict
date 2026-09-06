"""
Phase 1: clean and reconcile groundwater level (h) sources.

Sources combined (State == "Tamil Nadu" only):
  - gwl_manual_quarterly_*_1950_1990, _1991_2020  (quarterly manual readings)
  - gwl_tel_6_hourly_*_1991_2020, _2021_2025, _2026_2030 (6-hourly telemetry)

Two things had to be resolved by inspection, not assumption -- see
STATUS.md Known Issues for the numbers behind each:

1. Sentinel/error values. Manual quarterly contains an exact sentinel
   value of 999 (54,164 occurrences, clearly a missing-data code, not a
   real 999m depth) plus only 13 other values above 200. Telemetry
   contains a sentinel of exactly -999.999 (4,643 occurrences) plus
   garbage outliers up to 4.1 million. A single symmetric threshold of
   |value| >= 200m is used to drop all of these -- it removes every
   sentinel/garbage value found while keeping the plausible range
   (post-filter manual max is 190m, telemetry max magnitude ~200m, both
   physically reasonable for Tamil Nadu terrain).

2. Sign convention. Manual quarterly values are mostly small positive
   numbers (25/50/75th pct = 3.89 / 6.67 / 10.85 m), consistent with the
   standard groundwater-board convention "depth to water level below
   ground, positive down". Telemetry values are mostly negative
   (25/50/75th pct = -10.17 / -6.03 / -3.29 m). The median magnitudes are
   close (6.67m vs 6.03m) once sign is flipped, which is the basis for
   treating telemetry as the same "depth below ground" quantity with the
   opposite sign convention (negative = below ground). This is an
   inferred convention, not a confirmed one from any data dictionary --
   flagged in STATUS.md and partially cross-checked below against the
   Rajya Sabha aggregate.

Output keeps native per-reading timestamps (not resampled to daily),
since groundwater level is the PINN's target variable `h` and the
telemetry resolution (6-hourly) is a meaningful part of the observation
density.
"""
import os
import pandas as pd

RAW_DIR = "data/raw"
STATION_TABLE_PATH = "data/processed/station_table.csv"
OUT_PATH = "data/processed/groundwater_level.csv"

SENTINEL_ABS_THRESHOLD = 200

FILES = [
    ("gwl_manual_quarterly_tamil-nadu-sw-gw_tn_1950_1990.csv", "Groundwater Level Quarterly Manual (meter)", "manual_quarterly", 1),
    ("gwl_manual_quarterly_tamil-nadu-sw-gw_tn_1991_2020.csv", "Groundwater Level Quarterly Manual (meter)", "manual_quarterly", 1),
    ("gwl_tel_6_hourly_tamil-nadu-sw-gw_tn_1991_2020.csv", "Groundwater Level Telemetry Quadridaily (meter)", "telemetry_6hourly", -1),
    ("gwl_tel_6_hourly_tamil_nadu_sw_gw_tn_2021_2025.csv", "Groundwater Level Telemetry 6 Hourly (meter)", "telemetry_6hourly", -1),
    ("gwl_tel_6_hourly_tamil_nadu_sw_gw_tn_2026_2030.csv", "Groundwater Level Telemetry 6 Hourly (meter)", "telemetry_6hourly", -1),
]


def load_and_standardize(fname, value_col, source_tag, sign):
    path = os.path.join(RAW_DIR, fname)
    df = pd.read_csv(path, usecols=["Station", "District", "State", "Data Acquisition Time", value_col])
    n0 = len(df)
    df = df[df["State"] == "Tamil Nadu"].copy()
    n_dropped_state = n0 - len(df)

    df = df.dropna(subset=[value_col])
    n_dropped_na = n0 - n_dropped_state - len(df)

    n_sentinel = (df[value_col].abs() >= SENTINEL_ABS_THRESHOLD).sum()
    df = df[df[value_col].abs() < SENTINEL_ABS_THRESHOLD]

    df["dt"] = pd.to_datetime(df["Data Acquisition Time"], format="%d-%m-%Y %H:%M", errors="coerce")
    n_bad_dates = df["dt"].isna().sum()
    df = df.dropna(subset=["dt"])

    print(f"{fname}: {n0} rows -> {len(df)} kept "
          f"(dropped {n_dropped_state} non-TN, {n_dropped_na} null readings, "
          f"{n_sentinel} sentinel/|v|>={SENTINEL_ABS_THRESHOLD}, {n_bad_dates} unparseable dates)")

    df["depth_to_water_m"] = sign * df[value_col]
    df["source"] = source_tag
    return df[["Station", "District", "dt", "depth_to_water_m", "source"]]


def reconcile_with_rajya_sabha(combined, station_table):
    rs = pd.read_csv(os.path.join(RAW_DIR, "RS_Session_257_AU_896_3.csv"))
    rs = rs[rs["District"] != "Total"]
    # "Year" is a string column that also contains a stray "Total" value
    # (a grand-total row distinct from the District=="Total" rows) -- coerce
    # and drop it rather than assume Year is already numeric.
    rs["Year"] = pd.to_numeric(rs["Year"], errors="coerce")
    rs = rs.dropna(subset=["Year"])
    rs["Year"] = rs["Year"].astype(int)
    mapping = pd.read_csv("data/processed/district_name_mapping.csv")
    rs_to_canon = dict(zip(
        mapping[mapping["source"] == "RS_Session_257_AU_896_3.csv"]["source_name"],
        mapping[mapping["source"] == "RS_Session_257_AU_896_3.csv"]["canonical_district"],
    ))
    rs["canonical_district"] = rs["District"].map(rs_to_canon)

    combined = combined.copy()
    combined["year"] = combined["dt"].dt.year

    print("\n--- Reconciliation vs Rajya Sabha aggregate (2019-2021) ---")
    print("Comparing % of readings in the two unambiguous depth bins RS reports "
          "('0 - 2' and '> 40' mbgl); the three middle RS columns have corrupted "
          "headers (see STATUS.md) and are skipped here.")
    rows = []
    for _, rs_row in rs.iterrows():
        year, district = rs_row["Year"], rs_row["canonical_district"]
        sub = combined[(combined["year"] == year) & (combined["canonical_district"] == district)]
        if sub.empty:
            continue
        n = len(sub)
        pct_0_2 = 100 * (sub["depth_to_water_m"].between(0, 2)).sum() / n
        pct_gt_40 = 100 * (sub["depth_to_water_m"] > 40).sum() / n
        rows.append({
            "district": district, "year": year, "n_nwic_readings": n,
            "nwic_pct_0_2": round(pct_0_2, 1), "rs_pct_0_2": rs_row["Depth to Water Level (mbgl) - 0 - 2 - %"],
            "nwic_pct_gt_40": round(pct_gt_40, 1), "rs_pct_gt_40": rs_row["Depth to Water Level (mbgl) - > 40 - %"],
        })
    cmp_df = pd.DataFrame(rows)
    if not cmp_df.empty:
        cmp_df["diff_0_2"] = (cmp_df["nwic_pct_0_2"] - cmp_df["rs_pct_0_2"]).abs()
        print(cmp_df.sort_values("diff_0_2", ascending=False).head(15).to_string(index=False))
        print(f"\nMean abs difference in '0-2m' %: {cmp_df['diff_0_2'].mean():.1f} pts across {len(cmp_df)} district-years")
    else:
        print("No overlapping district-years found for comparison.")
    return cmp_df


def main():
    station_table = pd.read_csv(STATION_TABLE_PATH)
    mapping = pd.read_csv("data/processed/district_name_mapping.csv")
    nwic_map = mapping[mapping["source"] == "NWIC"][["source_name", "canonical_district"]].rename(columns={"source_name": "District"})

    frames = [load_and_standardize(f, col, tag, sign) for f, col, tag, sign in FILES]
    combined = pd.concat(frames, ignore_index=True)
    print(f"\nCombined rows before district join: {len(combined)}")

    combined = combined.merge(
        station_table.rename(columns={"Station": "Station_lookup"}),
        left_on=["Station", "District"],
        right_on=["Station_lookup", "canonical_district"],
        how="left",
    )
    unmapped = combined[combined["canonical_district"].isna()]
    if not unmapped.empty:
        print(f"WARNING: {len(unmapped)} rows had no (Station, District) match in station_table.csv, dropping")
        combined = combined.dropna(subset=["canonical_district"])

    combined = combined[["canonical_district", "Station", "latitude", "longitude", "dt", "depth_to_water_m", "source"]]
    combined = combined.sort_values(["canonical_district", "Station", "dt"]).reset_index(drop=True)

    os.makedirs("data/processed", exist_ok=True)
    combined.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(combined)} rows to {OUT_PATH}")
    print(f"Date range: {combined['dt'].min()} .. {combined['dt'].max()}")
    print(f"Districts covered: {combined['canonical_district'].nunique()}")
    print(f"Stations covered: {combined['Station'].nunique()}")
    print(combined.groupby("source").size())

    reconcile_with_rajya_sabha(combined, station_table)


if __name__ == "__main__":
    main()
