#!/usr/bin/env python3
"""Build town-level sign maps for good_school_within_1km effects.

Outputs:
1) Static PNG for documentation.
2) Folium HTML for optional interactive viewing.
3) Town-level coefficient summary CSV.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from shapely.geometry import Point

import folium


REPO_ROOT = Path(__file__).resolve().parents[2]

INPUT_RESALE = REPO_ROOT / "primary_boundaries" / "outputs" / "onemap" / "resale_flats_with_school_buffer_counts_onemap.csv"
INPUT_POINTS = REPO_ROOT / "primary_boundaries" / "outputs" / "resale_address_points_matched_with_school_counts.geojson"
INPUT_HDB_POLYGONS = REPO_ROOT / "primary_boundaries" / "inputs" / "HDBExistingBuilding.geojson"
INPUT_PLANNING_BOUNDARIES = REPO_ROOT / "primary_boundaries" / "inputs" / "MasterPlan2019PlanningAreaBoundaryNoSea.geojson"

OUTPUT_DIR = REPO_ROOT / "docs" / "assets"
OUTPUT_FIGURE = OUTPUT_DIR / "figures" / "town_good_school_within_1km_sign_static.png"
OUTPUT_MAP = OUTPUT_DIR / "maps" / "town_good_school_within_1km_sign_folium.html"
OUTPUT_CSV = OUTPUT_DIR / "data" / "town_good_school_within_1km_sign_summary.csv"
OUTPUT_MAPPING_CSV = OUTPUT_DIR / "data" / "town_to_planning_area_match.csv"


def parse_storey_mid(value: object) -> float:
    if pd.isna(value):
        return np.nan
    numbers = [int(number) for number in re.findall(r"\d+", str(value))]
    if not numbers:
        return np.nan
    if len(numbers) == 1:
        return float(numbers[0])
    return float(sum(numbers[:2]) / 2)


def safe_upper(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["town"] = safe_upper(work["town"])
    work["month_dt"] = pd.to_datetime(work["month"], format="%Y-%m", errors="coerce")
    work["month_period"] = work["month_dt"].dt.to_period("M").astype(str)
    work["lease_commence_date"] = pd.to_numeric(work["lease_commence_date"], errors="coerce")
    work["floor_area_sqm"] = pd.to_numeric(work["floor_area_sqm"], errors="coerce")
    work["resale_price"] = pd.to_numeric(work["resale_price"], errors="coerce")
    work["storey_mid"] = work["storey_range"].apply(parse_storey_mid)
    work["lease_age_years"] = work["month_dt"].dt.year - work["lease_commence_date"]

    for column in [
        "nearest_mall_walking_distance_m",
        "nearest_mrt_walking_distance_m",
        "malls_within_10min_walk",
        "mrt_unique_lines_within_10min_walk",
        "school_count_1km",
        "school_count_2km",
        "good_school_count_1km",
    ]:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    work["good_school_within_1km"] = (work["good_school_count_1km"] > 0).astype(int)
    work["ln_nearest_mall_walking_distance_m"] = np.log(work["nearest_mall_walking_distance_m"].clip(lower=1))
    work["ln_nearest_mrt_walking_distance_m"] = np.log(work["nearest_mrt_walking_distance_m"].clip(lower=1))
    work["log_resale_price"] = np.log(work["resale_price"].clip(lower=1))

    required = [
        "town",
        "flat_type",
        "flat_model",
        "month_period",
        "floor_area_sqm",
        "lease_age_years",
        "storey_mid",
        "ln_nearest_mall_walking_distance_m",
        "malls_within_10min_walk",
        "ln_nearest_mrt_walking_distance_m",
        "mrt_unique_lines_within_10min_walk",
        "school_count_1km",
        "school_count_2km",
        "good_school_within_1km",
        "log_resale_price",
    ]

    return work.dropna(subset=required).copy()


def fit_town_models(df: pd.DataFrame, min_rows: int = 500) -> pd.DataFrame:
    formula = (
        "log_resale_price ~ good_school_within_1km + floor_area_sqm + lease_age_years + storey_mid + "
        "ln_nearest_mall_walking_distance_m + malls_within_10min_walk + "
        "ln_nearest_mrt_walking_distance_m + mrt_unique_lines_within_10min_walk + "
        "school_count_1km + school_count_2km + C(flat_type) + C(flat_model) + C(month_period)"
    )

    rows: list[dict[str, object]] = []
    for town, chunk in df.groupby("town", sort=True):
        if len(chunk) < min_rows:
            continue
        try:
            model = smf.ols(formula, data=chunk).fit()
            if "good_school_within_1km" not in model.params.index:
                continue
            coef = float(model.params["good_school_within_1km"])
            p_value = float(model.pvalues["good_school_within_1km"])
            premium_pct = float(math.exp(coef) - 1)
            if abs(coef) < 1e-6:
                sign = "Zero"
            else:
                sign = "Positive" if coef > 0 else "Negative"

            rows.append(
                {
                    "town": town,
                    "n_obs": int(len(chunk)),
                    "coef_good_school_within_1km": coef,
                    "p_value": p_value,
                    "premium_pct": premium_pct,
                    "sign": sign,
                    "significant_5pct": bool(p_value < 0.05),
                }
            )
        except Exception:
            continue

    return pd.DataFrame(rows).sort_values("town").reset_index(drop=True)


def build_town_centroids(points_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(points_path)
    gdf["town"] = safe_upper(gdf["town"])
    grouped = (
        gdf.groupby("town", as_index=False)
        .agg(latitude=("latitude", "mean"), longitude=("longitude", "mean"))
    )
    grouped["geometry"] = grouped.apply(lambda row: Point(float(row["longitude"]), float(row["latitude"])), axis=1)
    return gpd.GeoDataFrame(grouped, geometry="geometry", crs="EPSG:4326")


def load_planning_boundaries(path: Path) -> gpd.GeoDataFrame:
    planning = gpd.read_file(path)[["PLN_AREA_N", "CA_IND", "geometry"]].copy()
    planning["planning_area"] = safe_upper(planning["PLN_AREA_N"])
    planning["CA_IND"] = planning["CA_IND"].astype(str).str.strip().str.upper()
    planning = planning.drop(columns=["PLN_AREA_N"])
    planning = planning[planning.geometry.notna() & ~planning.geometry.is_empty].copy()
    planning["geometry"] = planning.geometry.buffer(0).simplify(0.00005, preserve_topology=True)
    return planning


def build_planning_area_render(
    town_results: pd.DataFrame,
    points_path: Path,
    planning_boundaries_path: Path,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    planning = load_planning_boundaries(planning_boundaries_path)
    planning_names = set(planning["planning_area"].tolist())

    town_df = town_results.copy()
    town_df["town"] = safe_upper(town_df["town"])

    exact = town_df[town_df["town"].isin(planning_names)].copy()
    exact["planning_area"] = exact["town"]
    exact["town_source"] = exact["town"]
    exact["match_method"] = "exact_name"
    exact["point_count_in_planning_area"] = np.nan
    exact["point_share_in_town"] = np.nan

    unmatched_towns = sorted(set(town_df["town"]) - set(exact["town"]))
    fallback = pd.DataFrame()
    if unmatched_towns:
        points = gpd.read_file(points_path, columns=["town", "geometry"])
        points["town"] = safe_upper(points["town"])
        points = points[points["town"].isin(unmatched_towns)].copy()
        if not points.empty:
            joined = gpd.sjoin(
                points,
                planning[["planning_area", "geometry"]],
                how="left",
                predicate="within",
            )
            counts = (
                joined.dropna(subset=["planning_area"])
                .groupby(["town", "planning_area"], as_index=False)
                .size()
                .rename(columns={"size": "point_count_in_planning_area"})
            )
            if not counts.empty:
                totals = (
                    counts.groupby("town", as_index=False)["point_count_in_planning_area"]
                    .sum()
                    .rename(columns={"point_count_in_planning_area": "point_count_total_town"})
                )
                counts = counts.merge(totals, on="town", how="left")
                counts["point_share_in_town"] = (
                    counts["point_count_in_planning_area"] / counts["point_count_total_town"]
                )
                fallback = town_df.merge(counts, on="town", how="inner")
                fallback["town_source"] = fallback["town"]
                fallback["match_method"] = "spatial_fallback"

    mapped = pd.concat([exact, fallback], ignore_index=True, sort=False)
    if mapped.empty:
        raise RuntimeError("No town results could be mapped to planning boundaries.")

    render = planning.merge(mapped, on="planning_area", how="left")
    render = render[render["sign"].notna()].copy()
    mapping_table = mapped[
        [
            "town_source",
            "planning_area",
            "match_method",
            "point_count_in_planning_area",
            "point_share_in_town",
            "n_obs",
            "coef_good_school_within_1km",
            "p_value",
            "premium_pct",
            "sign",
            "significant_5pct",
        ]
    ].copy()
    return render, mapping_table


def draw_static_map(town_areas: gpd.GeoDataFrame, planning_boundaries_path: Path, output_png: Path) -> None:
    planning_base = load_planning_boundaries(planning_boundaries_path)
    color_map = {"Positive": "#2e7d32", "Negative": "#c62828", "Zero": "#616161"}
    render = town_areas.copy()
    render["color"] = render["sign"].map(color_map).fillna("#616161")

    fig, ax = plt.subplots(figsize=(10, 8))
    planning_base.plot(ax=ax, facecolor="#f5f5f5", edgecolor="#b0bec5", linewidth=0.6)
    render.plot(ax=ax, color=render["color"], edgecolor="#37474f", linewidth=0.8, alpha=0.55, zorder=3)

    labels = render.copy()
    labels["label_point"] = labels.representative_point()
    for _, row in labels.iterrows():
        point = row["label_point"]
        ax.text(point.x, point.y, row["planning_area"], fontsize=5.8, color="#1f1f1f", ha="center")

    ax.set_title("Planning-Area Sign of good_school_within_1km Coefficient", fontsize=12)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    minx, miny, maxx, maxy = planning_base.total_bounds
    ax.set_xlim(minx - 0.01, maxx + 0.01)
    ax.set_ylim(miny - 0.01, maxy + 0.01)

    legend_handles = [
        plt.Line2D([0], [0], marker="s", color="w", label="Positive", markerfacecolor="#2e7d32", markeredgecolor="black", markersize=8),
        plt.Line2D([0], [0], marker="s", color="w", label="Negative", markerfacecolor="#c62828", markeredgecolor="black", markersize=8),
        plt.Line2D([0], [0], marker="s", color="w", label="Zero", markerfacecolor="#616161", markeredgecolor="black", markersize=8),
    ]
    ax.legend(handles=legend_handles, loc="lower left", frameon=True)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_png, dpi=180)
    plt.close(fig)


def draw_folium_map(town_areas: gpd.GeoDataFrame, output_html: Path) -> None:
    m = folium.Map(location=[1.35, 103.82], zoom_start=11, tiles="cartodbpositron")

    color_map = {"Positive": "#2e7d32", "Negative": "#c62828", "Zero": "#616161"}

    render = town_areas.copy()
    render["premium_pct_display"] = (render["premium_pct"] * 100).round(2).astype(str) + "%"
    render["p_value_display"] = render["p_value"].map(lambda value: f"{value:.4g}")
    render["n_obs_display"] = render["n_obs"].map(lambda value: f"{int(value):,}")
    render["significant_5pct_display"] = render["significant_5pct"].map(lambda value: "Yes" if value else "No")
    render["point_count_display"] = render["point_count_in_planning_area"].apply(
        lambda value: "-" if pd.isna(value) else f"{int(value):,}"
    )
    render["point_share_display"] = render["point_share_in_town"].apply(
        lambda value: "-" if pd.isna(value) else f"{value:.1%}"
    )

    def style_function(feature: dict) -> dict:
        sign = feature["properties"].get("sign", "Zero")
        color = color_map.get(sign, "#616161")
        return {
            "fillColor": color,
            "color": "#37474f",
            "weight": 1.0,
            "fillOpacity": 0.45,
        }

    tooltip = folium.GeoJsonTooltip(
        fields=[
            "planning_area",
            "town_source",
            "match_method",
            "sign",
            "premium_pct_display",
            "p_value_display",
            "n_obs_display",
            "point_count_display",
            "point_share_display",
            "significant_5pct_display",
        ],
        aliases=[
            "Planning area",
            "Town source",
            "Match method",
            "Sign",
            "Premium",
            "p-value",
            "Observations",
            "Matched points in this area",
            "Share of town points",
            "Significant at 5%",
        ],
        localize=True,
        sticky=True,
    )

    folium.GeoJson(render.to_json(), style_function=style_function, tooltip=tooltip, name="Town sign areas").add_to(m)

    minx, miny, maxx, maxy = render.total_bounds
    m.fit_bounds([[miny, minx], [maxy, maxx]])
    folium.LayerControl(collapsed=False).add_to(m)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_html))


def main() -> None:
    if not INPUT_RESALE.exists():
        raise FileNotFoundError(f"Missing input resale dataset: {INPUT_RESALE}")
    if not INPUT_POINTS.exists():
        raise FileNotFoundError(f"Missing matched point dataset: {INPUT_POINTS}")
    if not INPUT_HDB_POLYGONS.exists():
        raise FileNotFoundError(f"Missing HDB polygon dataset: {INPUT_HDB_POLYGONS}")
    if not INPUT_PLANNING_BOUNDARIES.exists():
        raise FileNotFoundError(f"Missing planning boundary dataset: {INPUT_PLANNING_BOUNDARIES}")

    resale_df = pd.read_csv(INPUT_RESALE, low_memory=False)
    model_df = engineer_features(resale_df)
    town_results = fit_town_models(model_df, min_rows=500)
    if town_results.empty:
        raise RuntimeError("No town-level models were estimated. Check input coverage.")

    planning_render, mapping_table = build_planning_area_render(
        town_results,
        INPUT_POINTS,
        INPUT_PLANNING_BOUNDARIES,
    )
    if planning_render.empty:
        raise RuntimeError("No overlap between planning boundaries and estimated town results.")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    town_results.to_csv(OUTPUT_CSV, index=False)
    mapping_table.to_csv(OUTPUT_MAPPING_CSV, index=False)

    draw_static_map(planning_render, INPUT_PLANNING_BOUNDARIES, OUTPUT_FIGURE)
    draw_folium_map(planning_render, OUTPUT_MAP)

    print(f"Wrote: {OUTPUT_CSV}")
    print(f"Wrote: {OUTPUT_MAPPING_CSV}")
    print(f"Wrote: {OUTPUT_FIGURE}")
    print(f"Wrote: {OUTPUT_MAP}")
    print(
        "Sign counts: "
        + ", ".join(
            f"{label}={count}" for label, count in town_results["sign"].value_counts().to_dict().items()
        )
    )


if __name__ == "__main__":
    main()
