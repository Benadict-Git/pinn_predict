"""
Phase 1 step 8: build data/processed/observations.csv, the labeled dataset
for the PINN's data-fitting loss.

Columns: x (lon), y (lat), t (days since 1970-01-01, float -- fractional
for the 6-hourly telemetry), district, h (depth to water table below
ground, meters, positive down -- see STATUS.md issue 1 on the sign
convention), R (recharge proxy, mm/day), Q (pumping relative index,
unitless, constant per district).

h comes from groundwater_level.csv (every cleaned manual + telemetry
reading, both sources kept, tagged by `source` column -- not deduplicated
or averaged, since the two sources are not confirmed to agree, see
STATUS.md issue 11). R is joined by (district, calendar date) from
recharge_daily.csv and is NaN wherever no humidity reading existed that
day (pre-2021-07-28, or outside the 26-district humidity network) --
NOT filled with 0, since that would fabricate a recharge value never
measured. Q is joined by district only (time-invariant, see
build_pumping.py).

IMPORTANT: h here is a "depth to water table" convention, not an absolute
hydraulic head elevation, because no DEM/ground-elevation data is
available in data/raw/ to convert depth-below-ground into a head relative
to a fixed datum. Phase 2 should be aware the PDE's grad(h) term uses
this depth convention (larger h = deeper water table = lower head), not
literal elevation -- flagged for a domain-expert check before Phase 2.
"""
import pandas as pd

EPOCH = pd.Timestamp("1970-01-01")

GWL_PATH = "data/processed/groundwater_level.csv"
RECHARGE_PATH = "data/processed/recharge_daily.csv"
PUMPING_PATH = "data/processed/pumping_proxy.csv"
OUT_PATH = "data/processed/observations.csv"


def main():
    gwl = pd.read_csv(GWL_PATH, parse_dates=["dt"])
    recharge = pd.read_csv(RECHARGE_PATH, parse_dates=["date"])
    pumping = pd.read_csv(PUMPING_PATH)

    print(f"Loaded {len(gwl)} groundwater readings, {len(recharge)} district-day recharge rows, "
          f"{len(pumping)} district pumping rows")

    gwl["date"] = gwl["dt"].dt.date
    recharge["date"] = recharge["date"].dt.date

    merged = gwl.merge(
        recharge[["canonical_district", "date", "recharge_mm"]],
        on=["canonical_district", "date"], how="left",
    )
    n_no_recharge = merged["recharge_mm"].isna().sum()
    print(f"{n_no_recharge} of {len(merged)} rows ({100 * n_no_recharge / len(merged):.1f}%) "
          f"have no recharge value for their (district, date) -- left as NaN, not filled")

    merged = merged.merge(pumping[["canonical_district", "Q_relative_index"]], on="canonical_district", how="left")
    n_no_pumping = merged["Q_relative_index"].isna().sum()
    if n_no_pumping:
        print(f"WARNING: {n_no_pumping} rows have no Q value (unexpected -- pumping_proxy.csv should cover all 38 districts)")

    merged["t"] = (merged["dt"] - EPOCH).dt.total_seconds() / 86400.0

    out = merged.rename(columns={
        "longitude": "x", "latitude": "y", "canonical_district": "district",
        "depth_to_water_m": "h", "recharge_mm": "R", "Q_relative_index": "Q",
    })[["x", "y", "t", "district", "h", "R", "Q", "source"]]

    out = out.dropna(subset=["x", "y", "t", "h"])
    out = out.sort_values(["district", "t"]).reset_index(drop=True)
    out.to_csv(OUT_PATH, index=False)

    print(f"\nWrote {len(out)} rows to {OUT_PATH}")
    print(f"t range: {out['t'].min():.1f} .. {out['t'].max():.1f} days since epoch "
          f"({EPOCH + pd.Timedelta(days=out['t'].min())} .. {EPOCH + pd.Timedelta(days=out['t'].max())})")
    print(f"Districts: {out['district'].nunique()}, rows with R present: {out['R'].notna().sum()} "
          f"({100 * out['R'].notna().mean():.1f}%)")
    print(out.groupby("source").size())


if __name__ == "__main__":
    main()
