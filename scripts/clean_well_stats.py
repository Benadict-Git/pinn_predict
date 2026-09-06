"""
Phase 1: clean the three data.gov.in 2018-19 well/irrigation snapshots
into one district-level table, data/processed/well_stats_2018_19.csv.

Each source file has one row per (pre-2019-split) district plus a
"State Total" aggregate row, which is dropped. District names are mapped
to canonical names via district_name_mapping.csv (these files use
"Kanniyakumari", "The Nilgiris", "Villupuram" etc. -- see STATUS.md issue
4).

Only a handful of already-aggregated columns are kept out of the ~170
raw columns across the three files -- the raw files break irrigation
area/well counts down by government/private, electrical/diesel/other
pump, and well sub-type (tube/bore/open/artisan/filter-point/...), which
is far more granularity than a district-year pumping *proxy* can use
(the goal here, per CLAUDE.md, is a rough approximation, not a detailed
irrigation-engineering breakdown). Kept columns:

  - total_net_irrigated_area_ha: net area irrigated by any well type
    (tube/bore + open + supplementary wells), from
    area_irrigated_by_wells_by_districts_in_tn_2018_19.csv
  - total_wells_irrigation: total wells (government + private, all
    types), from number_source_of_irrigation_through_wells_tn_2018_19.csv
  - total_wells_domestic / total_wells_industrial / total_wells_not_in_use:
    from classification_of_usage_of_wells_for_domestic_and_industrial_purposes_by_districts_in_tn_2018_19.csv
"""
import os
import pandas as pd

RAW_DIR = "data/raw"
MAPPING_PATH = "data/processed/district_name_mapping.csv"
OUT_PATH = "data/processed/well_stats_2018_19.csv"

DROP_VALUES = {"State Total", "Total", ""}


def canonical_lookup(source_file):
    mapping = pd.read_csv(MAPPING_PATH)
    sub = mapping[mapping["source"] == source_file]
    return dict(zip(sub["source_name"], sub["canonical_district"]))


def load_area_irrigated():
    fname = "area_irrigated_by_wells_by_districts_in_tn_2018_19.csv"
    df = pd.read_csv(os.path.join(RAW_DIR, fname))
    df = df[~df["District"].isin(DROP_VALUES)]
    lookup = canonical_lookup(fname)
    df["canonical_district"] = df["District"].map(lookup)

    net_cols = [
        "Net Area irrigated by Government Tube Wells / Bore Wells (in ha)",
        "Net Area irrigated by Private Tube Wells / Bore Wells (in ha)",
        "Net Area irrigated by Government Open Wells (in ha)",
        "Net Area irrigated by Private Open Wells (in ha)",
        "Net Area irrigated by Government Supplementary Wells (by all other types of Wells) (in ha)",
        "Net Area irrigated by Private Supplementary Wells (by all other types of Wells) (in ha)",
    ]
    df["total_net_irrigated_area_ha"] = df[net_cols].sum(axis=1)
    print(f"{fname}: {len(df)} districts, total_net_irrigated_area_ha sum = {df['total_net_irrigated_area_ha'].sum():,.0f} ha")
    return df[["canonical_district", "total_net_irrigated_area_ha"]]


def load_number_source():
    fname = "number_source_of_irrigation_through_wells_tn_2018_19.csv"
    df = pd.read_csv(os.path.join(RAW_DIR, fname))
    df = df[~df["District"].isin(DROP_VALUES)]
    lookup = canonical_lookup(fname)
    df["canonical_district"] = df["District"].map(lookup)

    col = "Total Number of Wells (Government and Private)"
    df["total_wells_irrigation"] = df[col]
    print(f"{fname}: {len(df)} districts, total_wells_irrigation sum = {df['total_wells_irrigation'].sum():,}")
    return df[["canonical_district", "total_wells_irrigation"]]


def load_classification():
    fname = "classification_of_usage_of_wells_for_domestic_and_industrial_purposes_by_districts_in_tn_2018_19.csv"
    df = pd.read_csv(os.path.join(RAW_DIR, fname))
    df = df[~df["District"].isin(DROP_VALUES)]
    lookup = canonical_lookup(fname)
    df["canonical_district"] = df["District"].map(lookup)

    df = df.rename(columns={
        "Total Number of Wells used for Domestic Purposes": "total_wells_domestic",
        "Total Number of Wells used for Industrial Purposes": "total_wells_industrial",
        "Number of Wells not in use": "total_wells_not_in_use",
    })
    print(f"{fname}: {len(df)} districts, domestic={df['total_wells_domestic'].sum():,}, "
          f"industrial={df['total_wells_industrial'].sum():,}, not_in_use={df['total_wells_not_in_use'].sum():,}")
    return df[["canonical_district", "total_wells_domestic", "total_wells_industrial", "total_wells_not_in_use"]]


def main():
    area = load_area_irrigated()
    number = load_number_source()
    classification = load_classification()

    merged = area.merge(number, on="canonical_district", how="outer") \
                 .merge(classification, on="canonical_district", how="outer")

    unmapped = merged[merged["canonical_district"].isna()]
    if not unmapped.empty:
        print(f"WARNING: {len(unmapped)} rows failed district mapping, dropping")
        merged = merged.dropna(subset=["canonical_district"])

    merged = merged.sort_values("canonical_district").reset_index(drop=True)
    os.makedirs("data/processed", exist_ok=True)
    merged.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(merged)} districts to {OUT_PATH}")
    print(f"Covers {merged['canonical_district'].nunique()} of 38 canonical districts "
          f"(remainder are the 6 post-2019-split districts with no 2018-19 figures -- "
          f"see pre2019_parent_district fallback in district_name_mapping.csv, applied in build_pumping.py)")


if __name__ == "__main__":
    main()
