"""
Phase 1: clean rainfall sources into a single daily station-day series.

Sources combined (all Tamil Nadu, State == "Tamil Nadu" only):
  - rainfall_manual_daily_tn_1991_2020, rainfall_manual_daily_tn_1961_1990
  - rainfall_manual_hr_tn_1991_2020 (tiny, 25 rows)
  - rainfall_tel_hr_tn_1991_2020 (tiny, 30 rows), _2021_2025, _2026_2030

Excluded: rainfall_manual_{daily,hr}_kl / _mh -- these tag stations near
the TN border as State=Kerala/Maharashtra; the "Maharashtra"/"Nashik" tag
in particular looks like a source labeling error (Nashik is nowhere near
TN) and the row counts are negligible (2-7 rows). See STATUS.md.

Key convention discovered by inspection, not assumed: the telemetry
rainfall gauges are event-based tipping-bucket sensors -- the minimum
non-zero reading is exactly 0.5mm and there is no reading logged for
hours/days with no rain. Absence of a row therefore means "zero rainfall
recorded", NOT "missing data" -- so no NaN-filling is needed or performed
for the telemetry series; daily totals are just the sum of whatever
readings exist that calendar day (0 if none).

Hourly series (manual and telemetry) are aggregated to daily totals by
summing all readings within a calendar day per station, to match the
manual-daily series' native resolution and to give observations.csv a
single daily-resolution rainfall column.

A per-reading threshold of 300mm is applied before aggregation to drop
physically implausible single-timestamp spikes (raw data contains values
up to 16,750mm at a single timestamp, ~50x the world hourly rainfall
record) -- these look like sensor/counter errors, not real rainfall.
Dropped rows are counted and logged, never silently zeroed.
"""
import os
import pandas as pd

RAW_DIR = "data/raw"
STATION_TABLE_PATH = "data/processed/station_table.csv"
OUT_PATH = "data/processed/rainfall_daily.csv"

DAILY_FILES = [
    ("rainfall_manual_daily_tamil-nadu-sw-gw_tn_1991_2020.csv", "Manual Daily Rainfall (mm)", "manual_daily"),
    ("rainfall_manual_daily_tamil-nadu-sw-gw_tn_1961_1990.csv", "Manual Daily Rainfall (mm)", "manual_daily"),
]

HOURLY_FILES = [
    ("rainfall_manual_hr_tamil-nadu-sw-gw_tn_1991_2020.csv", "Manual Hourly Rainfall (mm)", "manual_hourly"),
    ("rainfall_tel_hr_tamil-nadu-sw-gw_tn_1991_2020.csv", "Telemetry Hourly Rainfall (mm)", "telemetry_hourly"),
    ("rainfall_tel_hr_tamil_nadu_sw_gw_tn_2021_2025.csv", "Telemetry Hourly Rainfall (mm)", "telemetry_hourly"),
    ("rainfall_tel_hr_tamil_nadu_sw_gw_tn_2026_2030.csv", "Telemetry Hourly Rainfall (mm)", "telemetry_hourly"),
]

MAX_PLAUSIBLE_READING_MM = 300


def load_and_standardize(fname, value_col, source_tag):
    path = os.path.join(RAW_DIR, fname)
    df = pd.read_csv(path, usecols=["Station", "District", "State", "Data Acquisition Time", value_col])
    n0 = len(df)
    df = df[df["State"] == "Tamil Nadu"].copy()
    n_dropped_state = n0 - len(df)

    n_negative = (df[value_col] < 0).sum()
    n_extreme = (df[value_col] > MAX_PLAUSIBLE_READING_MM).sum()
    df = df[(df[value_col] >= 0) & (df[value_col] <= MAX_PLAUSIBLE_READING_MM)]

    df["dt"] = pd.to_datetime(df["Data Acquisition Time"], format="%d-%m-%Y %H:%M", errors="coerce")
    n_bad_dates = df["dt"].isna().sum()
    df = df.dropna(subset=["dt"])
    df["date"] = df["dt"].dt.date

    print(f"{fname}: {n0} rows -> {len(df)} kept "
          f"(dropped {n_dropped_state} non-TN, {n_negative} negative, "
          f"{n_extreme} > {MAX_PLAUSIBLE_READING_MM}mm/reading, {n_bad_dates} unparseable dates)")

    df = df.rename(columns={value_col: "rainfall_mm"})
    df["source"] = source_tag
    return df[["Station", "District", "date", "rainfall_mm", "source"]]


def main():
    station_table = pd.read_csv(STATION_TABLE_PATH)

    frames = []
    for fname, value_col, tag in DAILY_FILES:
        frames.append(load_and_standardize(fname, value_col, tag))
    for fname, value_col, tag in HOURLY_FILES:
        raw = load_and_standardize(fname, value_col, tag)
        daily = raw.groupby(["Station", "District", "date", "source"], as_index=False)["rainfall_mm"].sum()
        frames.append(daily)

    combined = pd.concat(frames, ignore_index=True)
    print(f"\nCombined rows before district join: {len(combined)}")

    combined = combined.merge(
        station_table.rename(columns={"Station": "Station_lookup"}),
        left_on=["Station", "District"],
        right_on=["Station_lookup", "canonical_district"],
        how="left",
    )
    # canonical_district from station_table wins; District (raw) was only
    # needed to disambiguate the (Station, District) join key.
    unmapped = combined[combined["canonical_district"].isna()]
    if not unmapped.empty:
        print(f"WARNING: {len(unmapped)} rows had no (Station, District) match in station_table.csv, dropping")
        combined = combined.dropna(subset=["canonical_district"])

    combined = combined[["canonical_district", "Station", "latitude", "longitude", "date", "rainfall_mm", "source"]]
    combined = combined.sort_values(["canonical_district", "Station", "date"]).reset_index(drop=True)

    # Same station+day sometimes has more than one source (e.g. manual and
    # telemetry both operating during an overlap window) -- keep both, do
    # not average, so downstream code can choose or the discrepancy is
    # visible.
    dupe_mask = combined.duplicated(subset=["Station", "date"], keep=False)
    n_dupe = dupe_mask.sum()
    if n_dupe:
        print(f"NOTE: {n_dupe} rows share (Station, date) across >1 source -- kept as separate rows, not averaged")

    os.makedirs("data/processed", exist_ok=True)
    combined.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(combined)} rows to {OUT_PATH}")
    print(f"Date range: {combined['date'].min()} .. {combined['date'].max()}")
    print(f"Districts covered: {combined['canonical_district'].nunique()}")
    print(f"Stations covered: {combined['Station'].nunique()}")


if __name__ == "__main__":
    main()
