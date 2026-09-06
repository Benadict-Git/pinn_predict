"""
Phase 1 step 3: build data/processed/district_name_mapping.csv.

Canonical district list and LGD codes are derived directly from the NWIC
raw files (see scripts/inspect_raw.py output / STATUS.md) -- not looked up
externally. Tamil Nadu has 38 districts post the 2019-2020 reorganization;
that is exactly the number of distinct District LGD Codes found across the
NWIC files when restricted to State == "Tamil Nadu".

Two LGD codes carry two spelling variants within the NWIC data itself:
  593: "Tiruvannamalai" / "Thiruvannamalai"
  594: "Thoothukudi" / "Tuticorin"
We pick the modern official spelling as canonical (Tiruvannamalai,
Thoothukudi).

The data.gov.in well/irrigation files (2018-19 snapshot) and the Rajya
Sabha file predate the split and have no LGD codes at all -- they use the
pre-2019 33-district scheme (32 districts + a "State Total"/"Total" row,
which we drop). Their district names are mapped to canonical names by
lookup, not LGD code.

Six modern districts did not exist in 2018-19 and were carved out of an
older parent district (public record of Tamil Nadu's administrative
history, not derived from any file here):
  Chengalpattu     <- Kancheepuram   (2019)
  Kallakurichi     <- Viluppuram     (2019)
  Ranipet          <- Vellore        (2019)
  Tirupathur       <- Vellore        (2019)
  Tenkasi          <- Tirunelveli    (2019)
  Mayiladuthurai   <- Nagapattinam   (2020)
For these, pre2019_parent_district records which 2018-19 well-stats row a
downstream script should fall back to when a per-district Q value is
needed and no post-split figure exists. This is an approximation and must
stay documented, not silently applied.
"""
import glob
import os
import pandas as pd

RAW_DIR = "data/raw"
OUT_PATH = "data/processed/district_name_mapping.csv"

WELLS_FILES = [
    "area_irrigated_by_wells_by_districts_in_tn_2018_19.csv",
    "classification_of_usage_of_wells_for_domestic_and_industrial_purposes_by_districts_in_tn_2018_19.csv",
    "number_source_of_irrigation_through_wells_tn_2018_19.csv",
]
RS_FILE = "RS_Session_257_AU_896_3.csv"

# Canonical spelling chosen where NWIC data itself contains two spellings
# for the same LGD code.
CANONICAL_OVERRIDE = {
    "Thiruvannamalai": "Tiruvannamalai",
    "Tuticorin": "Thoothukudi",
}

# data.gov.in / Rajya Sabha spellings -> canonical NWIC spelling.
DATA_GOV_IN_TO_CANONICAL = {
    "Kanniyakumari": "Kanyakumari",
    "The Nilgiris": "Nilgiris",
    "Villupuram": "Viluppuram",
    "Thoothukudi": "Thoothukudi",
}


def to_canonical(name):
    # Chain both lookups: a non-NWIC spelling may also be one of the two
    # variant spellings found within the NWIC data itself (e.g. RS file
    # uses "Tuticorin" and "Thiruvannamalai").
    return CANONICAL_OVERRIDE.get(DATA_GOV_IN_TO_CANONICAL.get(name, name), DATA_GOV_IN_TO_CANONICAL.get(name, name))


# Rows that are aggregate totals, not districts -- drop.
DROP_VALUES = {"State Total", "Total", ""}

PRE2019_PARENT = {
    "Chengalpattu": "Kancheepuram",
    "Kallakurichi": "Viluppuram",
    "Ranipet": "Vellore",
    "Tirupathur": "Vellore",
    "Tenkasi": "Tirunelveli",
    "Mayiladuthurai": "Nagapattinam",
}


def collect_nwic_district_lgd_pairs():
    exclude = set(WELLS_FILES) | {RS_FILE}
    files = [
        f for f in glob.glob(os.path.join(RAW_DIR, "*.csv"))
        if "(1)" not in f and os.path.basename(f) not in exclude
    ]
    pairs = set()
    for f in files:
        try:
            df = pd.read_csv(f, usecols=["District", "District LGD Code", "State"])
        except ValueError:
            continue  # file has no District/LGD/State columns (e.g. well-stats-shaped files, already excluded)
        df = df[df["State"] == "Tamil Nadu"]
        for d, lgd in df[["District", "District LGD Code"]].drop_duplicates().itertuples(index=False):
            pairs.add((str(d), int(lgd)))
    return pairs


def main():
    os.makedirs("data/processed", exist_ok=True)

    pairs = collect_nwic_district_lgd_pairs()
    print(f"Collected {len(pairs)} (District, LGD Code) pairs from NWIC files (Tamil Nadu only)")

    rows = []
    lgd_to_canonical = {}
    for name, lgd in sorted(pairs):
        canonical = CANONICAL_OVERRIDE.get(name, name)
        lgd_to_canonical[lgd] = canonical
        rows.append({
            "canonical_district": canonical,
            "lgd_code": lgd,
            "source_name": name,
            "source": "NWIC",
            "pre2019_parent_district": PRE2019_PARENT.get(canonical, ""),
        })

    n_canonical = len(set(lgd_to_canonical.values()))
    print(f"Resolved to {n_canonical} canonical districts (expect 38)")
    assert n_canonical == 38, f"expected 38 canonical TN districts, got {n_canonical}"

    # data.gov.in well-stats files: no LGD code, pre-2019 33-row scheme.
    for fname in WELLS_FILES:
        df = pd.read_csv(os.path.join(RAW_DIR, fname), usecols=["District"])
        for name in sorted(df["District"].unique()):
            if name in DROP_VALUES:
                print(f"  dropping aggregate row '{name}' from {fname}")
                continue
            canonical = to_canonical(name)
            rows.append({
                "canonical_district": canonical,
                "lgd_code": "",
                "source_name": name,
                "source": fname,
                "pre2019_parent_district": "",
            })

    # Rajya Sabha file: same pre-2019-style names, separate source tag.
    df_rs = pd.read_csv(os.path.join(RAW_DIR, RS_FILE), usecols=["District"])
    for name in sorted(df_rs["District"].unique()):
        if name in DROP_VALUES:
            print(f"  dropping aggregate row '{name}' from {RS_FILE}")
            continue
        canonical = to_canonical(name)
        rows.append({
            "canonical_district": canonical,
            "lgd_code": "",
            "source_name": name,
            "source": RS_FILE,
            "pre2019_parent_district": "",
        })

    out = pd.DataFrame(rows).drop_duplicates()
    out = out.sort_values(["canonical_district", "source"]).reset_index(drop=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} rows to {OUT_PATH}")

    unmapped_canonical = set(out["canonical_district"]) - set(lgd_to_canonical.values())
    if unmapped_canonical:
        print(f"WARNING: canonical districts with no NWIC LGD code (pre-2019-only names, expected for split districts' parents is fine): {sorted(unmapped_canonical)}")


if __name__ == "__main__":
    main()
