"""
Phase 1 step 3 (cont.): build data/processed/station_table.csv, a
(Station, canonical_district) -> lat / lon lookup used by every cleaning
script. Built only from NWIC files (the only ones with per-station
lat/lon); joined against district_name_mapping.csv for canonical names.

Station name alone is NOT a unique key: many station names recur across
*unrelated* districts (e.g. "Vellore" appears as a station name inside
Vellore, Virudhunagar, and Thanjavur districts -- these are distinct
physical wells that happen to share a common place name, common in India).
The composite key here is (Station, canonical_district). Downstream
cleaning scripts must join on both fields together, never on Station name
alone, or they will silently conflate unrelated wells.

A (Station, District) pair can recur across multiple NWIC files (manual +
telemetry, different year ranges) with identical or near-identical
lat/lon -- we keep the first non-null lat/lon seen and log any pair whose
lat/lon disagrees by more than ~0.01 deg (~1km) across files, rather than
silently averaging or picking one.

Source data also contains a garbage station literally named "#REF!" (an
Excel formula-error artifact baked into the CSV export) recurring across
18 districts -- dropped entirely, not treated as a real well.
"""
import glob
import os
import pandas as pd

RAW_DIR = "data/raw"
MAPPING_PATH = "data/processed/district_name_mapping.csv"
OUT_PATH = "data/processed/station_table.csv"

EXCLUDE = {
    "area_irrigated_by_wells_by_districts_in_tn_2018_19.csv",
    "classification_of_usage_of_wells_for_domestic_and_industrial_purposes_by_districts_in_tn_2018_19.csv",
    "number_source_of_irrigation_through_wells_tn_2018_19.csv",
    "RS_Session_257_AU_896_3.csv",
}

INVALID_STATION_NAMES = {"#REF!"}

LAT_LON_TOLERANCE_DEG = 0.01


def main():
    mapping = pd.read_csv(MAPPING_PATH)
    nwic_map = mapping[mapping["source"] == "NWIC"][["source_name", "lgd_code", "canonical_district"]]
    nwic_map = nwic_map.rename(columns={"source_name": "District"})

    files = [
        f for f in glob.glob(os.path.join(RAW_DIR, "*.csv"))
        if "(1)" not in f and os.path.basename(f) not in EXCLUDE
    ]

    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, usecols=["Station", "District", "State", "Latitude", "Longitude"])
        except ValueError:
            continue
        df = df[df["State"] == "Tamil Nadu"].dropna(subset=["Latitude", "Longitude"])
        frames.append(df[["Station", "District", "Latitude", "Longitude"]])

    all_rows = pd.concat(frames, ignore_index=True)
    print(f"Collected {len(all_rows)} station observations with lat/lon across {len(files)} files")

    n_invalid = all_rows["Station"].isin(INVALID_STATION_NAMES).sum()
    if n_invalid:
        print(f"Dropping {n_invalid} rows with invalid/garbage station name(s) {INVALID_STATION_NAMES}")
        all_rows = all_rows[~all_rows["Station"].isin(INVALID_STATION_NAMES)]

    all_rows = all_rows.merge(nwic_map, on="District", how="left")
    unmapped = all_rows[all_rows["canonical_district"].isna()]
    if not unmapped.empty:
        print(f"WARNING: {unmapped['District'].nunique()} district name(s) had no mapping: {sorted(unmapped['District'].unique())}")
        all_rows = all_rows.dropna(subset=["canonical_district"])

    # Composite key: Station name alone is not unique (recurs across
    # unrelated districts), so group by (Station, canonical_district).
    grouped = all_rows.groupby(["Station", "canonical_district"])
    rows = []
    n_flagged = 0
    for (station, district), grp in grouped:
        lat_range = grp["Latitude"].max() - grp["Latitude"].min()
        lon_range = grp["Longitude"].max() - grp["Longitude"].min()
        if lat_range > LAT_LON_TOLERANCE_DEG or lon_range > LAT_LON_TOLERANCE_DEG:
            n_flagged += 1
        rows.append({
            "Station": station,
            "canonical_district": district,
            "latitude": grp["Latitude"].iloc[0],
            "longitude": grp["Longitude"].iloc[0],
            "lat_lon_disagreement_deg": max(lat_range, lon_range),
        })

    print(f"{n_flagged} (Station, District) pair(s) have lat/lon disagreement > {LAT_LON_TOLERANCE_DEG} deg across files (kept first-seen value, flagged in output column)")

    out = pd.DataFrame(rows).sort_values(["Station", "canonical_district"]).reset_index(drop=True)
    os.makedirs("data/processed", exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} unique (Station, District) pairs to {OUT_PATH}")
    dupe_station_names = out["Station"].duplicated().sum()
    print(f"{dupe_station_names} station name(s) recur across more than one district (expected -- see module docstring)")
    print(f"Stations by district (top 5): {out['canonical_district'].value_counts().head().to_dict()}")


if __name__ == "__main__":
    main()
