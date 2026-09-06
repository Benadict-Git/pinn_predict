"""
Phase 1 step 8 (cont.): build data/processed/collocation.csv, dense
unlabeled points for the PDE-residual loss.

Columns: x (lon), y (lat), t (days since 1970-01-01), district, R, Q --
same as observations.csv minus h, since these are synthetic locations,
not real wells.

Spatial grid: a regular 30x30 grid over the bounding box of every known
NWIC station (lat 8.10-13.54, lon 76.42-80.33, from station_table.csv),
900 points. Each grid point is assigned to the canonical district whose
station centroid (mean lat/lon of that district's stations) is nearest in
plain lat/lon distance. This is a rough nearest-centroid approximation,
NOT a true polygon/shapefile lookup -- no district boundary shapefile
exists in data/raw/, so points near a district border may be assigned to
the wrong neighbor. Flagged here and in DATA_DICTIONARY.md.

Temporal grid: monthly timestamps (month start) spanning the window where
recharge_daily.csv actually has valid (non-NaN) values anywhere --
2021-09-28 .. 2026-05-30 (see build_recharge.py; humidity, and therefore
R, does not exist before 2021-07-28). Collocation points outside this
window would have undefined R, so the grid is not extended further back
to match observations.csv's much longer 1972-2026 span.

R per (district, month) is the mean of recharge_daily's daily values in
that month for that district -- more robust than picking one arbitrary
day. R is only valid for the 26 districts with humidity coverage; for the
other 12 of 38 districts R is left NaN (not fabricated) exactly as in
observations.csv. Q is the constant per-district value from
pumping_proxy.csv, defined for all 38 districts.
"""
import numpy as np
import pandas as pd

STATION_TABLE_PATH = "data/processed/station_table.csv"
RECHARGE_PATH = "data/processed/recharge_daily.csv"
PUMPING_PATH = "data/processed/pumping_proxy.csv"
OUT_PATH = "data/processed/collocation.csv"

EPOCH = pd.Timestamp("1970-01-01")
GRID_N = 30


def nearest_district(lat, lon, centroids):
    d2 = (centroids["latitude"] - lat) ** 2 + (centroids["longitude"] - lon) ** 2
    return centroids.loc[d2.idxmin(), "canonical_district"]


def main():
    station_table = pd.read_csv(STATION_TABLE_PATH)
    recharge = pd.read_csv(RECHARGE_PATH, parse_dates=["date"])
    pumping = pd.read_csv(PUMPING_PATH)

    centroids = station_table.groupby("canonical_district", as_index=False)[["latitude", "longitude"]].mean()
    print(f"Computed {len(centroids)} district centroids from station_table.csv")

    lat_min, lat_max = station_table["latitude"].min(), station_table["latitude"].max()
    lon_min, lon_max = station_table["longitude"].min(), station_table["longitude"].max()
    lats = np.linspace(lat_min, lat_max, GRID_N)
    lons = np.linspace(lon_min, lon_max, GRID_N)
    grid = pd.DataFrame([(lat, lon) for lat in lats for lon in lons], columns=["latitude", "longitude"])
    grid["canonical_district"] = grid.apply(lambda r: nearest_district(r["latitude"], r["longitude"], centroids), axis=1)
    print(f"Built {len(grid)} spatial grid points ({GRID_N}x{GRID_N}) over lat [{lat_min:.2f},{lat_max:.2f}] "
          f"lon [{lon_min:.2f},{lon_max:.2f}], assigned via nearest district centroid")

    valid_recharge = recharge.dropna(subset=["recharge_mm"])
    t_start, t_end = valid_recharge["date"].min(), valid_recharge["date"].max()
    months = pd.date_range(t_start.replace(day=1), t_end, freq="MS")
    print(f"Temporal grid: {len(months)} monthly steps from {months.min().date()} to {months.max().date()}")

    recharge["month"] = recharge["date"].values.astype("datetime64[M]")
    monthly_recharge = recharge.groupby(["canonical_district", "month"], as_index=False)["recharge_mm"].mean()

    rows = []
    for month in months:
        month_grid = grid.copy()
        month_grid["month"] = month
        rows.append(month_grid)
    full = pd.concat(rows, ignore_index=True)
    print(f"Total collocation points before joins: {len(full)}")

    full = full.merge(monthly_recharge, on=["canonical_district", "month"], how="left")
    full = full.merge(pumping[["canonical_district", "Q_relative_index"]], on="canonical_district", how="left")

    full["t"] = (full["month"] - EPOCH).dt.total_seconds() / 86400.0

    out = full.rename(columns={
        "longitude": "x", "latitude": "y", "canonical_district": "district",
        "recharge_mm": "R", "Q_relative_index": "Q",
    })[["x", "y", "t", "district", "R", "Q"]]

    out.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(out)} rows to {OUT_PATH}")
    print(f"Rows with R present: {out['R'].notna().sum()} ({100 * out['R'].notna().mean():.1f}%) "
          f"-- expect ~{26}/38 districts' worth")
    print(f"Rows with Q present: {out['Q'].notna().sum()} ({100 * out['Q'].notna().mean():.1f}%)")


if __name__ == "__main__":
    main()
