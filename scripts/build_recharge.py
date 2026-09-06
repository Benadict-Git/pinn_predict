"""
Phase 1: build the recharge proxy R(x,y,t) from rainfall_daily.csv and
humidity_daily.csv, output to data/processed/recharge_daily.csv.

No temperature data exists anywhere in data/raw/ (see STATUS.md), so the
standard Hargreaves ET0 formula (needs Tmax/Tmin + extraterrestrial
radiation) cannot be computed. This uses a deliberately simple substitute,
not a validated ET model:

    et_proxy_mm = ET_K * (100 - humidity_pct)

i.e. evapotranspiration proxy scales linearly with the "dryness" of the
air (100 - RH%). ET_K = 0.1 was chosen so that typical Tamil Nadu humidity
readings (roughly 30-95% RH) map to a plausible daily ET range of about
0.5-7mm/day -- a sanity-check calibration, not a derived physical
constant. If temperature or ERA5-Land data becomes available later, this
should be replaced with a real ET formula rather than tuned further.

    recharge_mm = max(rainfall_mm - et_proxy_mm, 0)

Clipped at zero because "recharge" is infiltration to the water table,
which cannot be negative -- a moisture deficit just means zero recharge
that day, not a withdrawal (that's what the Q term and the S*dh/dt
response already capture).

Rainfall and humidity come from different station networks (198 vs 45
stations) with limited spatial overlap, so both are first aggregated to a
district-day mean before combining -- a district-level daily proxy, not a
per-station value. Humidity only exists from 2021-07-28 onward; days
before that have rainfall but no recharge estimate and are kept with
recharge_mm = NaN rather than assuming ET = 0, which would silently
overstate recharge for the pre-2021 period.
"""
import pandas as pd

RAINFALL_PATH = "data/processed/rainfall_daily.csv"
HUMIDITY_PATH = "data/processed/humidity_daily.csv"
OUT_PATH = "data/processed/recharge_daily.csv"

ET_K = 0.1


def main():
    rainfall = pd.read_csv(RAINFALL_PATH, parse_dates=["date"])
    humidity = pd.read_csv(HUMIDITY_PATH, parse_dates=["date"])

    rainfall_district = rainfall.groupby(["canonical_district", "date"], as_index=False)["rainfall_mm"].mean()
    humidity_district = humidity.groupby(["canonical_district", "date"], as_index=False)["humidity_pct"].mean()
    print(f"District-day rainfall rows: {len(rainfall_district)} ({rainfall_district['canonical_district'].nunique()} districts)")
    print(f"District-day humidity rows: {len(humidity_district)} ({humidity_district['canonical_district'].nunique()} districts)")

    merged = rainfall_district.merge(humidity_district, on=["canonical_district", "date"], how="left")
    n_no_humidity = merged["humidity_pct"].isna().sum()
    print(f"{n_no_humidity} of {len(merged)} district-days have rainfall but no humidity reading "
          f"(expected for dates before 2021-07-28, or districts outside the 26-district humidity network) "
          f"-- et_proxy_mm and recharge_mm left as NaN for these, not assumed zero")

    merged["et_proxy_mm"] = ET_K * (100 - merged["humidity_pct"])
    merged["recharge_mm"] = (merged["rainfall_mm"] - merged["et_proxy_mm"]).clip(lower=0)

    merged = merged.sort_values(["canonical_district", "date"]).reset_index(drop=True)
    merged.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(merged)} rows to {OUT_PATH}")
    print(f"Rows with a computed recharge_mm value: {merged['recharge_mm'].notna().sum()} "
          f"({100 * merged['recharge_mm'].notna().mean():.1f}%)")
    print(f"Date range: {merged['date'].min()} .. {merged['date'].max()}")


if __name__ == "__main__":
    main()
