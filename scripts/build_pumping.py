"""
Phase 1: build the pumping/extraction proxy Q(district) from
well_stats_2018_19.csv, output to data/processed/pumping_proxy.csv.

This is explicitly a *rough, time-invariant, unitless relative index*, not
a volumetric pumping rate (m3/day) -- the source data has no metered
extraction volumes, only well counts and irrigated area, and there is no
reliable conversion factor from either of those to an actual pumping
volume without fabricating one. Q_relative_index is built as an
unweighted mean of three independently min-max-normalized components:

  - total_net_irrigated_area_ha  (irrigation is the dominant TN groundwater use)
  - total_wells_irrigation
  - total_wells_domestic + total_wells_industrial

Equal weighting is an assumption, not a fit -- there is no data here to
calibrate relative weights (e.g. actual crop water demand or per-well
discharge rates). Document as such; do not read Q_relative_index as
"twice the district = twice the pumping in m3."

The 2018-19 snapshot predates the 2019-2020 Tamil Nadu district split.
The six post-split districts (Chengalpattu, Kallakurichi, Mayiladuthurai,
Ranipet, Tenkasi, Tirupathur) have no 2018-19 row of their own --
district_name_mapping.csv's pre2019_parent_district column is used to
copy the parent district's *same* absolute figures to the child. This
means the parent and child rows are NOT independent and summing
Q_relative_index (or its underlying components) across all 38 districts
double-counts the split-off area/wells -- acceptable for a per-district
approximation but flagged here and in DATA_DICTIONARY.md so it is never
used as a statewide total.

Output is one row per canonical district (38 rows), with no year column,
by design: the source is a single 2018-19 snapshot and the spec calls for
a rough district-level proxy, not a fabricated time trend. Downstream
code (build_collocation_grid.py / merge_datasets.py) is responsible for
broadcasting this constant value across whatever years/timestamps it
joins against.
"""
import pandas as pd

WELL_STATS_PATH = "data/processed/well_stats_2018_19.csv"
MAPPING_PATH = "data/processed/district_name_mapping.csv"
OUT_PATH = "data/processed/pumping_proxy.csv"


def minmax(s):
    return (s - s.min()) / (s.max() - s.min())


def main():
    well_stats = pd.read_csv(WELL_STATS_PATH)
    mapping = pd.read_csv(MAPPING_PATH)

    parent_lookup = mapping[mapping["pre2019_parent_district"].notna() & (mapping["pre2019_parent_district"] != "")]
    parent_lookup = parent_lookup[["canonical_district", "pre2019_parent_district"]].drop_duplicates()
    print(f"Districts needing pre-2019 parent fallback: {parent_lookup.to_dict('records')}")

    rows = [well_stats]
    for _, row in parent_lookup.iterrows():
        child, parent = row["canonical_district"], row["pre2019_parent_district"]
        parent_row = well_stats[well_stats["canonical_district"] == parent]
        if parent_row.empty:
            print(f"WARNING: no 2018-19 stats found for parent '{parent}' (needed for child '{child}'), skipping")
            continue
        child_row = parent_row.copy()
        child_row["canonical_district"] = child
        rows.append(child_row)
        print(f"  {child} <- copied from parent '{parent}' (same absolute figures, see module docstring on double-counting)")

    full = pd.concat(rows, ignore_index=True)
    assert full["canonical_district"].nunique() == 38, f"expected 38 districts, got {full['canonical_district'].nunique()}"

    full["domestic_industrial_wells"] = full["total_wells_domestic"] + full["total_wells_industrial"]
    full["_norm_area"] = minmax(full["total_net_irrigated_area_ha"])
    full["_norm_irrigation_wells"] = minmax(full["total_wells_irrigation"])
    full["_norm_dom_ind_wells"] = minmax(full["domestic_industrial_wells"])
    full["Q_relative_index"] = full[["_norm_area", "_norm_irrigation_wells", "_norm_dom_ind_wells"]].mean(axis=1)

    out = full[["canonical_district", "total_net_irrigated_area_ha", "total_wells_irrigation",
                "domestic_industrial_wells", "Q_relative_index"]].sort_values("canonical_district").reset_index(drop=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(out)} districts to {OUT_PATH}")
    print(f"Q_relative_index range: {out['Q_relative_index'].min():.3f} .. {out['Q_relative_index'].max():.3f}")
    print(out.sort_values("Q_relative_index", ascending=False).head(5)[["canonical_district", "Q_relative_index"]])


if __name__ == "__main__":
    main()
