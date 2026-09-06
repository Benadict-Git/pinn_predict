"""
Phase 1: clean relative humidity telemetry into a daily station-day mean.

Sources: humid_tele_hr_*_2021_2021 .. _2024_2024, humid_tel_hr_*_2025_2025,
_2026_2030 -- all Tamil Nadu, 45 stations, 26 districts, hourly, no
missing values as reported by inspect_raw.py.

Relative humidity is physically bounded to [0, 100]%, but raw readings go
as high as 1007% -- a sensor/unit error, not a real reading. Values
outside [0, 100] are dropped (not clipped, since clipping would fabricate
a value that was never measured) and counted.

Pressure telemetry (pressure_tel_hr_*) covers the same stations/dates and
looks physically plausible (932.5-1018.4 mb, all sane for Tamil Nadu) but
is not currently consumed by any physics term (R, Q, or h) -- left
uncleaned per CLAUDE.md, available for a future revision of the recharge
proxy if needed.
"""
import os
import pandas as pd

RAW_DIR = "data/raw"
STATION_TABLE_PATH = "data/processed/station_table.csv"
OUT_PATH = "data/processed/humidity_daily.csv"

FILES = [
    "humid_tele_hr_tamil-nadu-sw-gw_tn_2021_2021.csv",
    "humid_tele_hr_tamil-nadu-sw-gw_tn_2022_2022.csv",
    "humid_tele_hr_tamil-nadu-sw-gw_tn_2023_2023.csv",
    "humid_tele_hr_tamil-nadu-sw-gw_tn_2024_2024.csv",
    "humid_tel_hr_tamil_nadu_sw_gw_tn_2025_2025.csv",
    "humid_tel_hr_tamil_nadu_sw_gw_tn_2026_2030.csv",
]
VALUE_COL = "Telemetry Hourly Relative Humidity (%)"


def load_and_standardize(fname):
    path = os.path.join(RAW_DIR, fname)
    df = pd.read_csv(path, usecols=["Station", "District", "State", "Data Acquisition Time", VALUE_COL])
    n0 = len(df)
    df = df[df["State"] == "Tamil Nadu"].copy()
    n_dropped_state = n0 - len(df)

    n_out_of_range = ((df[VALUE_COL] < 0) | (df[VALUE_COL] > 100)).sum()
    df = df[(df[VALUE_COL] >= 0) & (df[VALUE_COL] <= 100)]

    df["dt"] = pd.to_datetime(df["Data Acquisition Time"], format="%d-%m-%Y %H:%M", errors="coerce")
    n_bad_dates = df["dt"].isna().sum()
    df = df.dropna(subset=["dt"])
    df["date"] = df["dt"].dt.date

    print(f"{fname}: {n0} rows -> {len(df)} kept "
          f"(dropped {n_dropped_state} non-TN, {n_out_of_range} outside [0,100]%, {n_bad_dates} unparseable dates)")

    return df.rename(columns={VALUE_COL: "humidity_pct"})[["Station", "District", "date", "humidity_pct"]]


def main():
    station_table = pd.read_csv(STATION_TABLE_PATH)

    frames = [load_and_standardize(f) for f in FILES]
    combined = pd.concat(frames, ignore_index=True)
    print(f"\nCombined rows before daily aggregation: {len(combined)}")

    daily = combined.groupby(["Station", "District", "date"], as_index=False)["humidity_pct"].mean()
    print(f"Rows after daily mean aggregation: {len(daily)}")

    daily = daily.merge(
        station_table.rename(columns={"Station": "Station_lookup"}),
        left_on=["Station", "District"],
        right_on=["Station_lookup", "canonical_district"],
        how="left",
    )
    unmapped = daily[daily["canonical_district"].isna()]
    if not unmapped.empty:
        print(f"WARNING: {len(unmapped)} rows had no (Station, District) match in station_table.csv, dropping")
        daily = daily.dropna(subset=["canonical_district"])

    daily = daily[["canonical_district", "Station", "latitude", "longitude", "date", "humidity_pct"]]
    daily = daily.sort_values(["canonical_district", "Station", "date"]).reset_index(drop=True)

    os.makedirs("data/processed", exist_ok=True)
    daily.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(daily)} rows to {OUT_PATH}")
    print(f"Date range: {daily['date'].min()} .. {daily['date'].max()}")
    print(f"Districts covered: {daily['canonical_district'].nunique()}")
    print(f"Stations covered: {daily['Station'].nunique()}")


if __name__ == "__main__":
    main()
