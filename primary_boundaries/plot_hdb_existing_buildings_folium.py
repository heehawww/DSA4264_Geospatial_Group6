#!/usr/bin/env python
"""Map HDB polygons with resale transaction points on an interactive Folium map.

Workflow:
1. Load HDB building polygons.
2. Build resale-address points from the resale CSV and geocode cache.
3. Spatially join points to polygons using point-within-polygon.
4. Keep only polygons that contain at least one point.
5. Include unmatched points (outside all polygons) as a separate layer.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import folium
import geopandas as gpd
import pandas as pd
from folium.plugins import Fullscreen, MiniMap


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.to_string().upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def style_hdb_polygon(_feature):
    return {
        "color": "#636363",
        "weight": 0.6,
        "fillColor": "#3182bd",
        "fillOpacity": 0.16,
    }


def style_unmatched_point(_feature):
    return {
        "radius": 4,
        "color": "#cb181d",
        "fillColor": "#ef3b2c",
        "fillOpacity": 0.92,
        "weight": 1,
    }


def style_matched_point(_feature):
    return {
        "radius": 3,
        "color": "#006d2c",
        "fillColor": "#31a354",
        "fillOpacity": 0.86,
        "weight": 1,
    }


def first_existing(columns: Iterable[str], candidates: list[str]) -> list[str]:
    cols = set(columns)
    return [c for c in candidates if c in cols]


def build_resale_points(
    resale_csv: Path,
    geocode_cache_csv: Path,
) -> gpd.GeoDataFrame:
    usecols = [
        "month",
        "town",
        "flat_type",
        "block",
        "street_name",
        "resale_price",
    ]
    resale_df = pd.read_csv(resale_csv, usecols=usecols)
    resale_df["town"] = resale_df["town"].astype(str).str.strip()
    resale_df["block"] = resale_df["block"].astype(str).str.strip()
    resale_df["street_name"] = resale_df["street_name"].astype(str).str.strip()
    resale_df["address_key"] = (
        resale_df["town"] + "|" + resale_df["block"] + "|" + resale_df["street_name"]
    )

    agg = (
        resale_df.groupby(["address_key", "town", "block", "street_name"], as_index=False)
        .agg(
            txn_count=("resale_price", "size"),
            avg_resale_price=("resale_price", "mean"),
            min_month=("month", "min"),
            max_month=("month", "max"),
        )
    )

    lat_col = "latitude" if "latitude" in resale_df.columns else None
    lon_col = "longitude" if "longitude" in resale_df.columns else None
    if lat_col and lon_col:
        points_df = (
            resale_df[["address_key", "town", "block", "street_name", lat_col, lon_col]]
            .dropna(subset=[lat_col, lon_col])
            .drop_duplicates(subset=["address_key"], keep="first")
            .rename(columns={lat_col: "latitude", lon_col: "longitude"})
        )
    else:
        if not geocode_cache_csv.exists():
            raise FileNotFoundError(
                "Resale CSV has no latitude/longitude columns and geocode cache was not found: "
                f"{geocode_cache_csv}"
            )
        cache_df = pd.read_csv(geocode_cache_csv)
        required = ["address_key", "latitude", "longitude"]
        missing = [c for c in required if c not in cache_df.columns]
        if missing:
            raise ValueError(f"Geocode cache missing required columns: {missing}")
        points_df = cache_df[required].copy()

    merged = agg.merge(points_df, on="address_key", how="left")
    merged = merged.dropna(subset=["latitude", "longitude"]).copy()

    points_gdf = gpd.GeoDataFrame(
        merged,
        geometry=gpd.points_from_xy(merged["longitude"], merged["latitude"]),
        crs="EPSG:4326",
    )
    return points_gdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Map HDB polygons with resale points on Folium")
    parser.add_argument(
        "--hdb-geojson",
        default=r"C:\Users\User\Downloads\HDBExistingBuilding.geojson",
        help="Path to HDB existing building GeoJSON",
    )
    parser.add_argument(
        "--resale-csv",
        default=r"C:\Users\User\Downloads\ResaleflatpricesbasedonregistrationdatefromJan2017onwards.csv",
        help="Path to HDB resale transactions CSV",
    )
    parser.add_argument(
        "--geocode-cache-csv",
        default=str(
            Path(__file__).resolve().parents[1]
            / "outputs"
            / "problem1"
            / "hdb_address_geocode_cache.csv"
        ),
        help="Address geocode cache CSV with latitude/longitude, used if resale CSV has no coords",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "outputs"),
        help="Output directory",
    )
    parser.add_argument(
        "--max-features",
        type=int,
        default=None,
        help="Optional cap on number of polygons (for faster preview)",
    )
    parser.add_argument(
        "--simplify-tolerance",
        type=float,
        default=0.0,
        help="Optional geometry simplify tolerance in degrees (e.g., 0.00001)",
    )
    args = parser.parse_args()

    src = Path(args.hdb_geojson)
    resale_csv = Path(args.resale_csv)
    geocode_cache_csv = Path(args.geocode_cache_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise FileNotFoundError(f"HDB GeoJSON not found: {src}")
    if not resale_csv.exists():
        raise FileNotFoundError(f"Resale CSV not found: {resale_csv}")

    print("Loading HDB polygons...")
    gdf = ensure_wgs84(gpd.read_file(src))
    total_polygons = len(gdf)

    if args.max_features is not None and args.max_features > 0:
        gdf = gdf.head(args.max_features).copy()

    if args.simplify_tolerance and args.simplify_tolerance > 0:
        gdf["geometry"] = gdf.geometry.simplify(args.simplify_tolerance, preserve_topology=True)

    print("Building resale points...")
    points_gdf = build_resale_points(
        resale_csv=resale_csv,
        geocode_cache_csv=geocode_cache_csv,
    )
    points_gdf = ensure_wgs84(points_gdf)
    points_gdf = points_gdf.reset_index(drop=True).copy()
    points_gdf["__point_id"] = points_gdf.index.astype(int)

    poly_id_col = "OBJECTID" if "OBJECTID" in gdf.columns else "__poly_id"
    if poly_id_col == "__poly_id":
        gdf = gdf.copy()
        gdf[poly_id_col] = gdf.index.astype(str)
    gdf = gdf.copy()
    gdf["__poly_area_m2"] = gdf.to_crs("EPSG:3414").geometry.area

    poly_cols = first_existing(
        gdf.columns,
        [poly_id_col, "BLK_NO", "POSTAL_COD", "ST_COD", "ENTITYID", "__poly_area_m2", "geometry"],
    )

    print("Running point-within-polygon join...")
    joined_points = gpd.sjoin(
        points_gdf,
        gdf[poly_cols],
        how="left",
        predicate="within",
    )
    # If a point intersects multiple overlapping polygons, pick one best match:
    # 1) matched polygon over null, 2) BLK_NO equals point block, 3) larger polygon area.
    joined_points["__has_match"] = joined_points[poly_id_col].notna().astype(int)
    if "BLK_NO" in joined_points.columns and "block" in joined_points.columns:
        joined_points["__blk_match"] = (
            joined_points["BLK_NO"].astype(str).str.upper()
            == joined_points["block"].astype(str).str.upper()
        ).astype(int)
    else:
        joined_points["__blk_match"] = 0
    joined_points["__poly_area_m2"] = pd.to_numeric(
        joined_points["__poly_area_m2"],
        errors="coerce",
    ).fillna(-1.0)
    joined_points = joined_points.sort_values(
        ["__point_id", "__has_match", "__blk_match", "__poly_area_m2"],
        ascending=[True, False, False, False],
    )
    joined_points = joined_points.drop_duplicates(subset=["__point_id"], keep="first")

    matched_points = joined_points[joined_points[poly_id_col].notna()].copy()
    unmatched_points = joined_points[joined_points[poly_id_col].isna()].copy()

    poly_stats = (
        matched_points.groupby(poly_id_col, as_index=False)
        .agg(
            matched_point_count=("address_key", "size"),
            matched_txn_count=("txn_count", "sum"),
            mean_avg_resale_price=("avg_resale_price", "mean"),
        )
    )
    matched_polygons = gdf.merge(poly_stats, on=poly_id_col, how="inner")
    matched_polygons = matched_polygons.drop(columns=["__poly_area_m2"], errors="ignore")

    # Save output layers.
    polygons_out = out_dir / "hdb_existing_buildings_layer.geojson"
    points_matched_out = out_dir / "hdb_resale_points_matched.geojson"
    points_unmatched_out = out_dir / "hdb_resale_points_unmatched.geojson"
    points_all_out = out_dir / "hdb_resale_points_all.geojson"

    matched_polygons.to_file(polygons_out, driver="GeoJSON")
    matched_points.to_file(points_matched_out, driver="GeoJSON")
    unmatched_points.to_file(points_unmatched_out, driver="GeoJSON")
    points_gdf.to_file(points_all_out, driver="GeoJSON")

    # Build interactive map.
    map_out = out_dir / "hdb_existing_buildings_map.html"
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=11, tiles="CartoDB positron")

    hdb_layer = folium.FeatureGroup(name="HDB polygons with resale points", show=True)
    matched_pts_layer = folium.FeatureGroup(name="Matched resale points (inside polygons)", show=False)
    unmatched_pts_layer = folium.FeatureGroup(name="Unmatched resale points (outside polygons)", show=True)

    tooltip_fields = first_existing(
        matched_polygons.columns,
        ["BLK_NO", "POSTAL_COD", poly_id_col, "ST_COD", "matched_point_count", "matched_txn_count"],
    )
    aliases_map = {
        "BLK_NO": "Block",
        "POSTAL_COD": "Postal Code",
        "OBJECTID": "ObjectID",
        "ST_COD": "Street Code",
        "__poly_id": "Polygon ID",
        "matched_point_count": "Matched point count",
        "matched_txn_count": "Matched txn count",
    }
    tooltip_aliases = [aliases_map.get(c, c) for c in tooltip_fields]

    folium.GeoJson(
        matched_polygons,
        name="HDB polygons",
        style_function=style_hdb_polygon,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True,
            sticky=False,
        ),
    ).add_to(hdb_layer)

    matched_point_fields = first_existing(
        matched_points.columns,
        ["town", "block", "street_name", "txn_count", "avg_resale_price", "max_month", poly_id_col],
    )
    matched_point_aliases_map = {
        "town": "Town",
        "block": "Block",
        "street_name": "Street",
        "txn_count": "Txn count",
        "avg_resale_price": "Avg resale price",
        "max_month": "Latest month",
        "OBJECTID": "Polygon ObjectID",
        "__poly_id": "Polygon ID",
    }
    folium.GeoJson(
        matched_points,
        name="Matched resale points",
        marker=folium.CircleMarker(),
        style_function=style_matched_point,
        tooltip=folium.GeoJsonTooltip(
            fields=matched_point_fields,
            aliases=[matched_point_aliases_map.get(c, c) for c in matched_point_fields],
            localize=True,
            sticky=False,
        ),
    ).add_to(matched_pts_layer)

    unmatched_point_fields = first_existing(
        unmatched_points.columns,
        ["town", "block", "street_name", "txn_count", "avg_resale_price", "max_month"],
    )
    unmatched_aliases_map = {
        "town": "Town",
        "block": "Block",
        "street_name": "Street",
        "txn_count": "Txn count",
        "avg_resale_price": "Avg resale price",
        "max_month": "Latest month",
    }
    folium.GeoJson(
        unmatched_points,
        name="Unmatched resale points",
        marker=folium.CircleMarker(),
        style_function=style_unmatched_point,
        tooltip=folium.GeoJsonTooltip(
            fields=unmatched_point_fields,
            aliases=[unmatched_aliases_map.get(c, c) for c in unmatched_point_fields],
            localize=True,
            sticky=False,
        ),
    ).add_to(unmatched_pts_layer)

    hdb_layer.add_to(m)
    matched_pts_layer.add_to(m)
    unmatched_pts_layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen(position="topright", title="Full Screen", title_cancel="Exit Full Screen").add_to(m)
    MiniMap(toggle_display=True).add_to(m)

    if len(matched_polygons) > 0:
        minx, miny, maxx, maxy = matched_polygons.total_bounds
        m.fit_bounds([[miny, minx], [maxy, maxx]])
    elif len(points_gdf) > 0:
        minx, miny, maxx, maxy = points_gdf.total_bounds
        m.fit_bounds([[miny, minx], [maxy, maxx]])

    m.save(str(map_out))

    print("Done.")
    print(f"Source polygons: {total_polygons}")
    print(f"Resale points built: {len(points_gdf)}")
    print(f"Matched points (within polygon): {len(matched_points)}")
    print(f"Unmatched points (outside polygons): {len(unmatched_points)}")
    print(f"Polygons retained after join: {len(matched_polygons)}")
    print(f"Saved polygon layer: {polygons_out}")
    print(f"Saved matched points layer: {points_matched_out}")
    print(f"Saved unmatched points layer: {points_unmatched_out}")
    print(f"Saved all points layer: {points_all_out}")
    print(f"Saved Folium map: {map_out}")


if __name__ == "__main__":
    main()
