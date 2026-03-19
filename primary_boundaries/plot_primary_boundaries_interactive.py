#!/usr/bin/env python
"""Create an interactive zoomable map for primary-school boundaries and points.

This script overlays GeoPandas layers on an interactive Singapore basemap.
Output is an HTML map with pan/zoom controls.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from folium.plugins import Fullscreen, MiniMap


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.to_string().upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def normalize_name(name: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())


def join_key(name: object) -> str:
    key = normalize_name(name)
    if key.endswith("PRIMARY"):
        key = key[: -len("PRIMARY")]
    return key


def style_polygon(feature):
    props = feature.get("properties", {}) if feature else {}
    is_good = props.get("is_good_school", False)
    if isinstance(is_good, str):
        is_good = is_good.lower() in {"1", "true", "yes"}
    elif isinstance(is_good, (int, float)):
        is_good = bool(is_good)

    if is_good:
        return {
            "color": "#238b45",
            "weight": 1.4,
            "fillColor": "#41ab5d",
            "fillOpacity": 0.34,
        }

    return {
        "color": "#1f78b4",
        "weight": 1.2,
        "fillColor": "#6baed6",
        "fillOpacity": 0.28,
    }


def style_buffer_1km(_feature):
    return {
        "color": "#2ca25f",
        "weight": 1.0,
        "fillColor": "#66c2a4",
        "fillOpacity": 0.12,
    }


def style_buffer_2km(_feature):
    return {
        "color": "#f16913",
        "weight": 1.0,
        "fillColor": "#fdae6b",
        "fillOpacity": 0.08,
    }


def make_buffer_polygons(boundaries: gpd.GeoDataFrame, distance_m: float) -> gpd.GeoDataFrame:
    b_proj = boundaries.to_crs("EPSG:3414").copy()
    b_proj["geometry"] = b_proj.geometry.buffer(distance_m)
    return b_proj.to_crs(boundaries.crs)


def apply_school_tiers(boundaries: gpd.GeoDataFrame, good_schools_csv: Path) -> tuple[gpd.GeoDataFrame, int]:
    gdf = boundaries.copy()
    gdf["join_key"] = gdf["school_name"].apply(join_key) if "school_name" in gdf.columns else ""

    if not good_schools_csv.exists():
        gdf["is_good_school"] = False
        gdf["school_tier"] = "normal"
        return gdf, 0

    good_df = pd.read_csv(good_schools_csv)
    if "join_key" in good_df.columns:
        good_keys = set(good_df["join_key"].astype(str).str.upper())
    elif "school_name" in good_df.columns:
        good_keys = set(good_df["school_name"].apply(join_key))
    else:
        good_keys = set()

    gdf["is_good_school"] = gdf["join_key"].astype(str).str.upper().isin(good_keys)
    gdf["school_tier"] = gdf["is_good_school"].map({True: "Good", False: "Normal"})
    return gdf, int(gdf["is_good_school"].sum())


def dedupe_boundaries_by_objectid(
    boundaries: gpd.GeoDataFrame,
    objectid_col: str = "OBJECTID",
) -> tuple[gpd.GeoDataFrame, int]:
    if objectid_col not in boundaries.columns:
        return boundaries, 0

    gdf = boundaries.copy()
    gdf["_area_m2"] = gdf.to_crs("EPSG:3414").geometry.area

    with_id = gdf[gdf[objectid_col].notna()].copy()
    without_id = gdf[gdf[objectid_col].isna()].copy()

    before = len(with_id)
    with_id = with_id.sort_values([objectid_col, "_area_m2"], ascending=[True, False])
    with_id = with_id.drop_duplicates(subset=[objectid_col], keep="first")
    removed = before - len(with_id)

    cleaned = pd.concat([with_id, without_id], ignore_index=True)
    cleaned = gpd.GeoDataFrame(cleaned, geometry="geometry", crs=gdf.crs).drop(columns=["_area_m2"])
    return cleaned, int(removed)


def reduce_multipolygon_to_school_component(
    boundaries: gpd.GeoDataFrame,
    points: gpd.GeoDataFrame,
    school_col: str = "school_name",
) -> tuple[gpd.GeoDataFrame, int]:
    if school_col not in boundaries.columns or school_col not in points.columns:
        return boundaries, 0

    # Work in meters for robust distance/area logic.
    b_proj = boundaries.to_crs("EPSG:3414").copy()
    p_proj = points.to_crs("EPSG:3414").copy()

    point_lookup = (
        p_proj.dropna(subset=[school_col])
        .drop_duplicates(subset=[school_col], keep="first")
        .set_index(school_col)["geometry"]
        .to_dict()
    )

    simplified_count = 0
    new_geoms = []

    for row in b_proj.itertuples(index=False):
        geom = getattr(row, "geometry", None)
        school_name = getattr(row, school_col, None)

        if geom is None or geom.is_empty:
            new_geoms.append(geom)
            continue

        if isinstance(geom, Polygon):
            new_geoms.append(geom)
            continue

        if isinstance(geom, MultiPolygon):
            parts = list(geom.geoms)
            if len(parts) <= 1:
                new_geoms.append(geom)
                continue

            school_pt = point_lookup.get(school_name)
            chosen = None

            if school_pt is not None:
                containing = [p for p in parts if p.covers(school_pt)]
                if containing:
                    chosen = max(containing, key=lambda p: p.area)
                else:
                    chosen = min(parts, key=lambda p: p.distance(school_pt))

            if chosen is None:
                chosen = max(parts, key=lambda p: p.area)

            new_geoms.append(chosen)
            simplified_count += 1
            continue

        # For non-polygon geometries, keep as-is.
        new_geoms.append(geom)

    b_proj["geometry"] = new_geoms
    cleaned = b_proj.to_crs(boundaries.crs)
    return cleaned, simplified_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive map for primary-school boundaries")
    parser.add_argument(
        "--boundaries-geojson",
        default=str(
            Path(__file__).resolve().parent
            / "outputs"
            / "primary_school_boundaries.geojson"
        ),
        help="GeoJSON polygons for school boundaries",
    )
    parser.add_argument(
        "--points-geojson",
        default=str(
            Path(__file__).resolve().parent
            / "outputs"
            / "primary_school_landuse_join_points.geojson"
        ),
        help="GeoJSON points for schools",
    )
    parser.add_argument(
        "--output-html",
        default=str(
            Path(__file__).resolve().parent
            / "outputs"
            / "primary_school_boundaries_interactive_map.html"
        ),
        help="Output interactive HTML map path",
    )
    parser.add_argument(
        "--cleaned-boundaries-out",
        default=str(
            Path(__file__).resolve().parent
            / "outputs"
            / "primary_school_boundaries_cleaned.geojson"
        ),
        help="Output cleaned polygons after OBJECTID deduplication",
    )
    parser.add_argument(
        "--good-schools-csv",
        default=str(
            Path(__file__).resolve().parent
            / "outputs"
            / "good_schools_top59.csv"
        ),
        help="CSV of top oversubscribed schools (good schools)",
    )
    parser.add_argument(
        "--buffer-1km-out",
        default=str(
            Path(__file__).resolve().parent
            / "outputs"
            / "primary_school_boundaries_buffer_1km.geojson"
        ),
        help="Output GeoJSON for 1km polygon buffers",
    )
    parser.add_argument(
        "--buffer-2km-out",
        default=str(
            Path(__file__).resolve().parent
            / "outputs"
            / "primary_school_boundaries_buffer_2km.geojson"
        ),
        help="Output GeoJSON for 2km polygon buffers",
    )
    args = parser.parse_args()

    boundaries_path = Path(args.boundaries_geojson)
    points_path = Path(args.points_geojson)
    output_html = Path(args.output_html)
    cleaned_out = Path(args.cleaned_boundaries_out)
    good_schools_csv = Path(args.good_schools_csv)
    buffer_1km_out = Path(args.buffer_1km_out)
    buffer_2km_out = Path(args.buffer_2km_out)
    output_html.parent.mkdir(parents=True, exist_ok=True)

    if not boundaries_path.exists():
        raise FileNotFoundError(f"Boundaries GeoJSON not found: {boundaries_path}")
    if not points_path.exists():
        raise FileNotFoundError(f"Points GeoJSON not found: {points_path}")

    print("Loading GeoPandas layers...")
    boundaries = ensure_wgs84(gpd.read_file(boundaries_path))
    points = ensure_wgs84(gpd.read_file(points_path))
    boundaries, simplified = reduce_multipolygon_to_school_component(
        boundaries,
        points,
        school_col="school_name",
    )
    boundaries, removed_dups = dedupe_boundaries_by_objectid(boundaries, objectid_col="OBJECTID")
    boundaries, good_count = apply_school_tiers(boundaries, good_schools_csv)
    boundaries.to_file(cleaned_out, driver="GeoJSON")
    buffer_1km = make_buffer_polygons(boundaries, distance_m=1000.0)
    buffer_2km = make_buffer_polygons(boundaries, distance_m=2000.0)
    buffer_1km.to_file(buffer_1km_out, driver="GeoJSON")
    buffer_2km.to_file(buffer_2km_out, driver="GeoJSON")

    # Initialize around Singapore; fit_bounds will refine viewport.
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=11, tiles="CartoDB positron")

    buffer_2km_layer = folium.FeatureGroup(name="2km polygon buffers", show=False)
    buffer_1km_layer = folium.FeatureGroup(name="1km polygon buffers", show=False)
    poly_layer = folium.FeatureGroup(name="Primary school boundary polygons", show=True)
    pts_layer = folium.FeatureGroup(name="Primary school points", show=True)

    folium.GeoJson(
        buffer_2km,
        name="2km buffers",
        style_function=style_buffer_2km,
        tooltip=folium.GeoJsonTooltip(
            fields=[c for c in ["school_name", "OBJECTID"] if c in buffer_2km.columns],
            aliases=["School", "URA ObjectID"],
            localize=True,
            sticky=True,
        ),
    ).add_to(buffer_2km_layer)

    folium.GeoJson(
        buffer_1km,
        name="1km buffers",
        style_function=style_buffer_1km,
        tooltip=folium.GeoJsonTooltip(
            fields=[c for c in ["school_name", "OBJECTID"] if c in buffer_1km.columns],
            aliases=["School", "URA ObjectID"],
            localize=True,
            sticky=True,
        ),
    ).add_to(buffer_1km_layer)

    folium.GeoJson(
        boundaries,
        name="School boundaries",
        style_function=style_polygon,
        tooltip=folium.GeoJsonTooltip(
            fields=[c for c in ["school_name", "school_tier", "LU_DESC", "OBJECTID"] if c in boundaries.columns],
            aliases=["School", "Tier", "Land-use", "URA ObjectID"],
            localize=True,
            sticky=True,
        ),
    ).add_to(poly_layer)

    for row in points.itertuples(index=False):
        geom = getattr(row, "geometry", None)
        if geom is None or geom.is_empty:
            continue

        school = getattr(row, "school_name", "Unknown school")
        tier = getattr(row, "school_tier", "normal")
        landuse = getattr(row, "LU_DESC", "Unknown")
        objectid = getattr(row, "OBJECTID", "")

        popup_html = (
            f"<b>{school}</b><br>"
            f"Tier: {tier}<br>"
            f"Land-use: {landuse}<br>"
            f"URA ObjectID: {objectid}"
        )

        marker_color = "#238b45" if str(tier).lower() == "good" else "#08519c"
        folium.CircleMarker(
            location=[geom.y, geom.x],
            radius=4,
            color=marker_color,
            weight=1,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.95,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=school,
        ).add_to(pts_layer)

    buffer_2km_layer.add_to(m)
    buffer_1km_layer.add_to(m)
    poly_layer.add_to(m)
    pts_layer.add_to(m)

    # Add convenience controls for exploration.
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen(position="topright", title="Full Screen", title_cancel="Exit Full Screen").add_to(m)
    MiniMap(toggle_display=True).add_to(m)

    # Fit map bounds to boundaries extent.
    minx, miny, maxx, maxy = boundaries.total_bounds
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    m.save(str(output_html))

    print("Done.")
    print(f"Polygons loaded: {len(boundaries)}")
    print(f"MultiPolygon geometries simplified: {simplified}")
    print(f"Duplicate OBJECTID polygons removed: {removed_dups}")
    print(f"Good-school polygons (top-59 mapping): {good_count}")
    print(f"Points loaded: {len(points)}")
    print(f"Saved cleaned boundaries: {cleaned_out}")
    print(f"Saved 1km buffers: {buffer_1km_out}")
    print(f"Saved 2km buffers: {buffer_2km_out}")
    print(f"Saved interactive map: {output_html}")


if __name__ == "__main__":
    main()
