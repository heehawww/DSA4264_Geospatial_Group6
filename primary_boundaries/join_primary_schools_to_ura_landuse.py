#!/usr/bin/env python
"""Step 1: Assign each primary school point to its containing URA land-use polygon.

This script performs a point-in-polygon spatial join using GeoPandas.

Outputs:
- primary_school_landuse_join_points.geojson  (school points + URA area attributes)
- primary_school_boundaries.geojson           (polygon geometry + school attributes)
- unmatched_primary_schools.csv               (schools not inside any polygon)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd


def detect_school_name_column(df: pd.DataFrame) -> str:
    candidates = ["school_name", "Name", "name", "SCHOOL_NAME"]
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(
        "Could not detect school name column. Expected one of: "
        + ", ".join(candidates)
    )


def build_primary_school_points(
    schools_csv: Path,
    lat_col: str,
    lon_col: str,
) -> gpd.GeoDataFrame:
    df = pd.read_csv(schools_csv)

    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(
            f"Latitude/longitude columns not found. Expected columns '{lat_col}' and '{lon_col}'."
        )

    school_col = detect_school_name_column(df)

    work = df.copy()
    work = work.dropna(subset=[lat_col, lon_col]).copy()

    # Keep only primary rows when such a column exists.
    if "mainlevel_code" in work.columns:
        work = work[work["mainlevel_code"].astype(str).str.contains("PRIMARY", case=False, na=False)]

    gdf = gpd.GeoDataFrame(
        work,
        geometry=gpd.points_from_xy(work[lon_col], work[lat_col]),
        crs="EPSG:4326",
    )

    # Standardize school name column for downstream steps.
    if school_col != "school_name":
        gdf = gdf.rename(columns={school_col: "school_name"})

    return gdf


def select_ura_columns(ura_gdf: gpd.GeoDataFrame) -> List[str]:
    preferred = [
        "OBJECTID",
        "LU_DESC",
        "LU_TEXT",
        "GPR",
        "WHI_Q_MX",
        "GPR_B_MN",
        "SHAPE.AREA",
        "SHAPE.LEN",
    ]
    cols = [c for c in preferred if c in ura_gdf.columns]
    return cols


def save_boundary_plot(
    matched_points: gpd.GeoDataFrame,
    unmatched_points: gpd.GeoDataFrame,
    boundaries_gdf: gpd.GeoDataFrame,
    plot_out: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 10))

    # Plot school-boundary polygons first.
    if len(boundaries_gdf) > 0:
        boundaries_gdf.plot(
            ax=ax,
            facecolor="#9ecae1",
            edgecolor="#3182bd",
            linewidth=0.6,
            alpha=0.35,
        )

    # Plot matched and unmatched school points.
    if len(matched_points) > 0:
        matched_points.plot(
            ax=ax,
            color="#08519c",
            markersize=12,
            marker="o",
            label="Matched schools",
            zorder=3,
        )

    if len(unmatched_points) > 0:
        unmatched_points.plot(
            ax=ax,
            color="#cb181d",
            markersize=30,
            marker="x",
            label="Unmatched schools",
            zorder=4,
        )

    ax.set_title("Primary Schools Joined to URA Land-Use Polygons", fontsize=13)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True, linewidth=0.2, alpha=0.4)
    ax.set_aspect("equal", adjustable="datalim")

    if len(unmatched_points) > 0:
        ax.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(plot_out, dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Join primary school points with containing URA land-use polygon"
    )
    parser.add_argument(
        "--schools-csv",
        default=r"C:\Users\User\Projects\primary school location\outputs\school_estate_summary.csv",
        help="CSV containing primary school locations with latitude/longitude",
    )
    parser.add_argument(
        "--lat-col",
        default="latitude",
        help="Latitude column in schools CSV",
    )
    parser.add_argument(
        "--lon-col",
        default="longitude",
        help="Longitude column in schools CSV",
    )
    parser.add_argument(
        "--ura-geojson",
        default=r"C:\Users\User\Downloads\MasterPlan2025LandUseLayer.geojson",
        help="URA land use GeoJSON",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "outputs"),
        help="Output directory",
    )
    parser.add_argument(
        "--join-predicate",
        default="within",
        choices=["within", "intersects", "contains"],
        help="Spatial join predicate",
    )
    parser.add_argument(
        "--plot-out",
        default=None,
        help="Output PNG for quick visual check (default: output-dir/primary_school_boundaries_plot.png)",
    )
    args = parser.parse_args()

    schools_csv = Path(args.schools_csv)
    ura_geojson = Path(args.ura_geojson)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not schools_csv.exists():
        raise FileNotFoundError(f"Schools CSV not found: {schools_csv}")
    if not ura_geojson.exists():
        raise FileNotFoundError(f"URA GeoJSON not found: {ura_geojson}")

    print("Loading school points...")
    schools_gdf = build_primary_school_points(schools_csv, args.lat_col, args.lon_col)
    print(f"Schools loaded: {len(schools_gdf)}")

    print("Loading URA polygons...")
    ura_gdf = gpd.read_file(ura_geojson)
    if ura_gdf.crs is None:
        ura_gdf = ura_gdf.set_crs("EPSG:4326")

    if schools_gdf.crs != ura_gdf.crs:
        schools_gdf = schools_gdf.to_crs(ura_gdf.crs)

    ura_cols = select_ura_columns(ura_gdf)
    ura_subset = ura_gdf[ura_cols + ["geometry"]].copy()

    print("Running spatial join...")
    joined = gpd.sjoin(
        schools_gdf,
        ura_subset,
        how="left",
        predicate=args.join_predicate,
    )

    matched = joined[joined["index_right"].notna()].copy()
    unmatched = joined[joined["index_right"].isna()].copy()

    # Build polygon-based entity: one row per matched school with polygon geometry.
    matched["index_right"] = matched["index_right"].astype(int)
    polygons_for_match = (
        ura_subset.reset_index()
        .rename(columns={"index": "index_right"})
        [["index_right"] + ura_cols + ["geometry"]]
    )

    boundaries = (
        matched.drop(columns=["geometry"])
        .merge(polygons_for_match, on=["index_right"] + ura_cols, how="left")
    )
    boundaries_gdf = gpd.GeoDataFrame(boundaries, geometry="geometry", crs=ura_subset.crs)

    # Keep one boundary per school if duplicates occur (first hit).
    if "school_name" in boundaries_gdf.columns:
        boundaries_gdf = boundaries_gdf.sort_values("school_name").drop_duplicates(subset=["school_name"], keep="first")

    # Export outputs.
    points_out = output_dir / "primary_school_landuse_join_points.geojson"
    boundaries_out = output_dir / "primary_school_boundaries.geojson"
    unmatched_out = output_dir / "unmatched_primary_schools.csv"
    plot_out = Path(args.plot_out) if args.plot_out else output_dir / "primary_school_boundaries_plot.png"

    joined.to_file(points_out, driver="GeoJSON")
    boundaries_gdf.to_file(boundaries_out, driver="GeoJSON")
    unmatched.drop(columns=["geometry"]).to_csv(unmatched_out, index=False, encoding="utf-8-sig")
    save_boundary_plot(matched, unmatched, boundaries_gdf, plot_out)

    print("Done.")
    print(f"Matched schools: {len(matched)}")
    print(f"Unmatched schools: {len(unmatched)}")
    print(f"Saved points join: {points_out}")
    print(f"Saved boundary polygons: {boundaries_out}")
    print(f"Saved unmatched list: {unmatched_out}")
    print(f"Saved plot: {plot_out}")


if __name__ == "__main__":
    main()
