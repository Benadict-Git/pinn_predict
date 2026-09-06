"""
Phase 1 step 10: sanity-check plots, saved to data/processed/plots/.
Purely diagnostic -- not part of the modeling pipeline.

1. rainfall_sample_station.png: daily rainfall vs time, one sample station.
2. gwl_manual_vs_telemetry.png: depth-to-water vs time for one station that
   has both a manual and a telemetry reading history, so the two sources'
   sign-corrected values can be visually compared (see STATUS.md issue 1).
3. wells_spatial_scatter.png: all station locations, colored by district.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = "data/processed/plots"
RAINFALL_STATION = "Madurai Airport"
GWL_STATION = "Ariyakudi"
GWL_DISTRICT = "Ramanathapuram"


def plot_rainfall():
    df = pd.read_csv("data/processed/rainfall_daily.csv", parse_dates=["date"])
    sub = df[df["Station"] == RAINFALL_STATION].sort_values("date")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(sub["date"], sub["rainfall_mm"], color="#2b6cb0", linewidth=0.7)
    ax.set_title(f"Daily rainfall — {RAINFALL_STATION}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Rainfall (mm)")
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "rainfall_sample_station.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"Saved {path} ({len(sub)} points for '{RAINFALL_STATION}')")


def plot_gwl_overlay():
    df = pd.read_csv("data/processed/groundwater_level.csv", parse_dates=["dt"])
    sub = df[(df["Station"] == GWL_STATION) & (df["canonical_district"] == GWL_DISTRICT)].sort_values("dt")
    fig, ax = plt.subplots(figsize=(10, 4))
    for source, color in [("manual_quarterly", "#c05621"), ("telemetry_6hourly", "#2f855a")]:
        s = sub[sub["source"] == source]
        ax.plot(s["dt"], s["depth_to_water_m"], label=source, color=color,
                marker="o" if source == "manual_quarterly" else None, markersize=3, linewidth=0.8)
    ax.invert_yaxis()  # deeper water table (larger value) plotted downward
    ax.set_title(f"Depth to water table — {GWL_STATION} ({GWL_DISTRICT})\n"
                 f"manual vs telemetry, telemetry sign-flipped to match manual convention")
    ax.set_xlabel("Date")
    ax.set_ylabel("Depth to water (m, positive = deeper)")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "gwl_manual_vs_telemetry.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"Saved {path} ({len(sub)} points for '{GWL_STATION}', {GWL_DISTRICT})")


def plot_spatial_scatter():
    st = pd.read_csv("data/processed/station_table.csv")
    fig, ax = plt.subplots(figsize=(7, 8))
    districts = sorted(st["canonical_district"].unique())
    cmap = plt.get_cmap("tab20", len(districts))
    color_map = {d: cmap(i) for i, d in enumerate(districts)}
    ax.scatter(st["longitude"], st["latitude"], c=[color_map[d] for d in st["canonical_district"]], s=6, alpha=0.7)
    ax.set_title(f"All NWIC station locations by district (n={len(st)})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "wells_spatial_scatter.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"Saved {path} ({len(st)} stations, {len(districts)} districts, legend omitted -- see district_name_mapping.csv for district list)")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plot_rainfall()
    plot_gwl_overlay()
    plot_spatial_scatter()


if __name__ == "__main__":
    main()
