#!/usr/bin/env python
"""Build a resale-flat dataset with school-buffer intersection counts.

For each resale transaction:
1. Geocode to a point (via lat/lon columns or address cache).
2. Keep only transactions whose point falls within an HDB polygon.
3. Count school-buffer intersections for the containing HDB polygon:
   - good_school_count_1km
   - good_school_count_2km
   - school_count_1km
   - school_count_2km
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd
from scipy.spatial import cKDTree


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.to_string().upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def first_existing(columns: Iterable[str], candidates: list[str]) -> list[str]:
    cols = set(columns)
    return [c for c in candidates if c in cols]


def is_true(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "good"}


def load_resale_with_points(
    resale_csv: Path,
    geocode_cache_csv: Path,
) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    resale_df = pd.read_csv(resale_csv)
    for col in ["town", "block", "street_name"]:
        if col not in resale_df.columns:
            raise ValueError(f"Resale CSV missing required column: {col}")
        resale_df[col] = resale_df[col].astype(str).str.strip()
    resale_df["address_key"] = (
        resale_df["town"] + "|" + resale_df["block"] + "|" + resale_df["street_name"]
    )

    if {"latitude", "longitude"}.issubset(resale_df.columns):
        coord_df = (
            resale_df[["address_key", "latitude", "longitude"]]
            .dropna(subset=["latitude", "longitude"])
            .drop_duplicates(subset=["address_key"], keep="first")
        )
    else:
        if not geocode_cache_csv.exists():
            raise FileNotFoundError(
                "Resale CSV has no latitude/longitude columns and geocode cache does not exist: "
                f"{geocode_cache_csv}"
            )
        cache_df = pd.read_csv(geocode_cache_csv)
        required = ["address_key", "latitude", "longitude"]
        missing = [c for c in required if c not in cache_df.columns]
        if missing:
            raise ValueError(f"Geocode cache missing required columns: {missing}")
        coord_df = cache_df[required].copy()

    address_points_df = (
        resale_df[["address_key", "town", "block", "street_name"]]
        .drop_duplicates(subset=["address_key"], keep="first")
        .merge(coord_df, on="address_key", how="left")
        .dropna(subset=["latitude", "longitude"])
        .copy()
    )

    points_gdf = gpd.GeoDataFrame(
        address_points_df,
        geometry=gpd.points_from_xy(address_points_df["longitude"], address_points_df["latitude"]),
        crs="EPSG:4326",
    )
    return resale_df, points_gdf


def assign_points_to_hdb_polygons(
    points_gdf: gpd.GeoDataFrame,
    hdb_gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, str]:
    points = ensure_wgs84(points_gdf).reset_index(drop=True).copy()
    polygons = ensure_wgs84(hdb_gdf).copy()

    points["__point_id"] = points.index.astype(int)

    poly_id_col = "OBJECTID" if "OBJECTID" in polygons.columns else "__poly_id"
    if poly_id_col == "__poly_id":
        polygons[poly_id_col] = polygons.index.astype(str)

    polygons["__poly_area_m2"] = polygons.to_crs("EPSG:3414").geometry.area

    poly_cols = first_existing(
        polygons.columns,
        [poly_id_col, "BLK_NO", "POSTAL_COD", "ST_COD", "ENTITYID", "__poly_area_m2", "geometry"],
    )

    joined = gpd.sjoin(
        points,
        polygons[poly_cols],
        how="left",
        predicate="within",
    )

    matched_points = joined[joined[poly_id_col].notna()].copy()
    unmatched_points = joined[joined[poly_id_col].isna()].copy()

    matched_poly_ids = matched_points[poly_id_col].dropna().unique().tolist()
    matched_polygons = polygons[polygons[poly_id_col].isin(matched_poly_ids)].copy()
    matched_polygons = matched_polygons.drop(columns=["__poly_area_m2"], errors="ignore")

    return matched_points, unmatched_points, matched_polygons, poly_id_col


def load_school_buffer(buffer_path: Path) -> gpd.GeoDataFrame:
    gdf = ensure_wgs84(gpd.read_file(buffer_path)).copy()

    if "is_good_school" in gdf.columns:
        good_series = gdf["is_good_school"].apply(is_true)
    elif "school_tier" in gdf.columns:
        good_series = gdf["school_tier"].astype(str).str.strip().str.lower().eq("good")
    else:
        good_series = pd.Series(False, index=gdf.index)

    if "join_key" in gdf.columns:
        school_id = gdf["join_key"].astype(str)
    elif "school_name" in gdf.columns:
        school_id = gdf["school_name"].astype(str)
    elif "OBJECTID" in gdf.columns:
        school_id = gdf["OBJECTID"].astype(str)
    else:
        school_id = gdf.index.astype(str)

    out = gdf.copy()
    out["__school_id"] = school_id
    out["__is_good_school"] = good_series
    return out[["__school_id", "__is_good_school", "geometry"]]


def count_school_intersections(
    polygons: gpd.GeoDataFrame,
    buffer_gdf: gpd.GeoDataFrame,
    poly_id_col: str,
    suffix: str,
) -> pd.DataFrame:
    if polygons.empty:
        return pd.DataFrame(
            columns=[poly_id_col, f"school_count_{suffix}", f"good_school_count_{suffix}"]
        )

    base = polygons[[poly_id_col, "geometry"]].copy()
    intersections = gpd.sjoin(
        base,
        buffer_gdf[["__school_id", "__is_good_school", "geometry"]],
        how="left",
        predicate="intersects",
    )

    intersections = intersections[intersections["__school_id"].notna()].copy()
    if intersections.empty:
        return base[[poly_id_col]].drop_duplicates().assign(
            **{
                f"school_count_{suffix}": 0,
                f"good_school_count_{suffix}": 0,
            }
        )

    total_counts = (
        intersections.groupby(poly_id_col)["__school_id"].nunique().rename(f"school_count_{suffix}")
    )
    good_counts = (
        intersections[intersections["__is_good_school"]]
        .groupby(poly_id_col)["__school_id"]
        .nunique()
        .rename(f"good_school_count_{suffix}")
    )

    out = (
        base[[poly_id_col]]
        .drop_duplicates()
        .merge(total_counts.reset_index(), on=poly_id_col, how="left")
        .merge(good_counts.reset_index(), on=poly_id_col, how="left")
        .fillna(0)
    )
    out[f"school_count_{suffix}"] = out[f"school_count_{suffix}"].astype(int)
    out[f"good_school_count_{suffix}"] = out[f"good_school_count_{suffix}"].astype(int)
    return out


def load_mall_points(mall_points_geojson: Path) -> gpd.GeoDataFrame:
    gdf = ensure_wgs84(gpd.read_file(mall_points_geojson)).copy()
    if gdf.empty:
        return gdf

    if "shopping_centre_name" not in gdf.columns:
        if "mall_name" in gdf.columns:
            gdf["shopping_centre_name"] = gdf["mall_name"].astype(str)
        elif "name" in gdf.columns:
            gdf["shopping_centre_name"] = gdf["name"].astype(str)
        else:
            gdf["shopping_centre_name"] = gdf.index.astype(str)

    gdf = gdf[gdf.geometry.notna() & (~gdf.geometry.is_empty)].copy()
    gdf = gdf.drop_duplicates(subset=["shopping_centre_name"], keep="first")
    return gdf[["shopping_centre_name", "geometry"]]


def add_mall_access_features(
    matched_points: gpd.GeoDataFrame,
    malls_gdf: gpd.GeoDataFrame,
    walk_distance_10min_m: float = 800.0,
    network_detour_factor: float = 1.0,
) -> gpd.GeoDataFrame:
    out = matched_points.copy()
    out["nearest_mall_name"] = pd.NA
    out["nearest_mall_walking_distance_m"] = pd.NA
    out["malls_within_10min_walk"] = 0

    if out.empty or malls_gdf.empty:
        return out
    if walk_distance_10min_m <= 0:
        raise ValueError("walk_distance_10min_m must be positive")
    if network_detour_factor <= 0:
        raise ValueError("network_detour_factor must be positive")

    pts_proj = out.to_crs("EPSG:3414").copy()
    malls_proj = malls_gdf.to_crs("EPSG:3414").copy()

    point_coords = list(zip(pts_proj.geometry.x.to_numpy(), pts_proj.geometry.y.to_numpy()))
    mall_coords = list(zip(malls_proj.geometry.x.to_numpy(), malls_proj.geometry.y.to_numpy()))

    tree = cKDTree(mall_coords)
    nearest_dist_euclidean_m, nearest_idx = tree.query(point_coords, k=1)

    # Approximate walking distance by scaling straight-line distance with a detour factor.
    nearest_dist_walk_m = nearest_dist_euclidean_m * network_detour_factor
    nearest_names = malls_proj.iloc[nearest_idx]["shopping_centre_name"].to_numpy()

    euclidean_radius_m = walk_distance_10min_m / network_detour_factor
    nearby_idx_lists = tree.query_ball_point(point_coords, r=euclidean_radius_m)
    nearby_counts = [len(idxs) for idxs in nearby_idx_lists]

    out["nearest_mall_name"] = nearest_names
    out["nearest_mall_walking_distance_m"] = nearest_dist_walk_m
    out["malls_within_10min_walk"] = nearby_counts
    out["nearest_mall_walking_distance_m"] = out["nearest_mall_walking_distance_m"].astype(float)
    out["malls_within_10min_walk"] = out["malls_within_10min_walk"].astype(int)
    return out


def normalize_station_name(value) -> str:
    return " ".join(str(value).upper().strip().split())


def parse_lines_value(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        # Try strict JSON first.
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

        # Fallback for Python-list-like strings.
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

        # Last fallback: split by comma.
        return [x.strip() for x in text.split(",") if x.strip()]

    # Handles list/tuple/set/ndarray-like objects.
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]

    return []


def load_mrt_exits_with_lines(mrt_tagged_geojson: Path) -> gpd.GeoDataFrame:
    gdf = ensure_wgs84(gpd.read_file(mrt_tagged_geojson)).copy()
    if gdf.empty:
        return gdf

    station_col = None
    for c in ["STATION_NA", "STATION_NAME_ENGLISH", "station_name"]:
        if c in gdf.columns:
            station_col = c
            break
    if station_col is None:
        raise ValueError("MRT GeoJSON missing station-name column (expected STATION_NA or STATION_NAME_ENGLISH)")

    # Prefer JSON-safe field if present.
    if "lines_present_json" in gdf.columns:
        parsed_lines = gdf["lines_present_json"].apply(parse_lines_value)
    elif "lines_present" in gdf.columns:
        parsed_lines = gdf["lines_present"].apply(parse_lines_value)
    else:
        parsed_lines = pd.Series([[] for _ in range(len(gdf))], index=gdf.index)

    out = gdf.copy()
    out["__station_name"] = gdf[station_col].apply(normalize_station_name)
    out["__lines_list"] = parsed_lines
    out = out[out.geometry.notna() & (~out.geometry.is_empty)].copy()
    return out[["__station_name", "__lines_list", "geometry"]]


def add_mrt_access_features(
    matched_points: gpd.GeoDataFrame,
    mrt_gdf: gpd.GeoDataFrame,
    walk_distance_10min_m: float = 800.0,
    network_detour_factor: float = 1.0,
) -> gpd.GeoDataFrame:
    out = matched_points.copy()
    out["nearest_mrt_station_name"] = pd.NA
    out["nearest_mrt_walking_distance_m"] = pd.NA
    out["mrt_unique_lines_within_10min_walk"] = 0

    if out.empty or mrt_gdf.empty:
        return out
    if walk_distance_10min_m <= 0:
        raise ValueError("walk_distance_10min_m must be positive")
    if network_detour_factor <= 0:
        raise ValueError("network_detour_factor must be positive")

    pts_proj = out.to_crs("EPSG:3414").copy()
    mrt_proj = mrt_gdf.to_crs("EPSG:3414").copy()

    point_coords = list(zip(pts_proj.geometry.x.to_numpy(), pts_proj.geometry.y.to_numpy()))
    mrt_coords = list(zip(mrt_proj.geometry.x.to_numpy(), mrt_proj.geometry.y.to_numpy()))
    tree = cKDTree(mrt_coords)

    nearest_dist_euclidean_m, nearest_idx = tree.query(point_coords, k=1)
    nearest_dist_walk_m = nearest_dist_euclidean_m * network_detour_factor
    nearest_station_names = mrt_proj.iloc[nearest_idx]["__station_name"].to_numpy()

    out["nearest_mrt_station_name"] = nearest_station_names
    out["nearest_mrt_walking_distance_m"] = nearest_dist_walk_m.astype(float)

    euclidean_radius_m = walk_distance_10min_m / network_detour_factor
    nearby_idx_lists = tree.query_ball_point(point_coords, r=euclidean_radius_m)

    station_values = mrt_proj["__station_name"].tolist()
    lines_values = mrt_proj["__lines_list"].tolist()

    unique_line_counts = []
    for idxs in nearby_idx_lists:
        station_lines_map: dict[str, set[str]] = {}
        for idx in idxs:
            station = station_values[idx]
            if station not in station_lines_map:
                station_lines_map[station] = set()
            for line_name in lines_values[idx]:
                if line_name:
                    station_lines_map[station].add(str(line_name).strip())

        visited_stations = set()
        unique_lines = set()
        for station, station_lines in station_lines_map.items():
            if station in visited_stations:
                continue
            visited_stations.add(station)
            unique_lines.update(station_lines)
        unique_line_counts.append(len(unique_lines))

    out["mrt_unique_lines_within_10min_walk"] = pd.Series(unique_line_counts, index=out.index).astype(int)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create resale-flat dataset with school counts from 1km/2km polygon-buffer intersections"
    )
    parser.add_argument(
        "--resale-csv",
        default=r"C:\Users\User\Downloads\ResaleflatpricesbasedonregistrationdatefromJan2017onwards.csv",
        help="Resale flat CSV path",
    )
    parser.add_argument(
        "--hdb-geojson",
        default=r"C:\Users\User\Downloads\HDBExistingBuilding.geojson",
        help="HDB polygon GeoJSON path",
    )
    parser.add_argument(
        "--geocode-cache-csv",
        default=str(
            Path(__file__).resolve().parents[1] / "outputs" / "problem1" / "hdb_address_geocode_cache.csv"
        ),
        help="Geocode cache for resale addresses",
    )
    parser.add_argument(
        "--school-buffer-1km",
        default=str(
            Path(__file__).resolve().parent / "outputs" / "primary_school_boundaries_buffer_1km.geojson"
        ),
        help="Primary school 1km buffer GeoJSON",
    )
    parser.add_argument(
        "--school-buffer-2km",
        default=str(
            Path(__file__).resolve().parent / "outputs" / "primary_school_boundaries_buffer_2km.geojson"
        ),
        help="Primary school 2km buffer GeoJSON",
    )
    parser.add_argument(
        "--mall-points-geojson",
        default=str(
            Path(__file__).resolve().parent / "outputs" / "shopping_centres_points.geojson"
        ),
        help="Shopping-centre points GeoJSON",
    )
    parser.add_argument(
        "--mrt-tagged-geojson",
        default=str(
            Path(__file__).resolve().parent / "outputs" / "mrt_exits_tagged_with_lines.geojson"
        ),
        help="Tagged MRT exits GeoJSON with line lists",
    )
    parser.add_argument(
        "--walk-distance-10min-m",
        type=float,
        default=800.0,
        help="Walking distance threshold (meters) for a 10-minute walk",
    )
    parser.add_argument(
        "--network-detour-factor",
        type=float,
        default=1.0,
        help="Multiplier converting straight-line to estimated walking path distance",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "outputs"),
        help="Output directory",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Output resale dataset CSV path",
    )
    parser.add_argument(
        "--matched-addresses-geojson",
        default=None,
        help="Optional GeoJSON for matched resale address points",
    )
    parser.add_argument(
        "--unmatched-addresses-geojson",
        default=None,
        help="Optional GeoJSON for unmatched resale address points",
    )
    parser.add_argument(
        "--point-count-by-postal-csv",
        default=None,
        help="Optional CSV output for matched resale address-point counts by polygon postal code",
    )
    args = parser.parse_args()

    resale_csv = Path(args.resale_csv)
    hdb_geojson = Path(args.hdb_geojson)
    geocode_cache_csv = Path(args.geocode_cache_csv)
    school_buffer_1km = Path(args.school_buffer_1km)
    school_buffer_2km = Path(args.school_buffer_2km)
    mall_points_geojson = Path(args.mall_points_geojson)
    mrt_tagged_geojson = Path(args.mrt_tagged_geojson)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not resale_csv.exists():
        raise FileNotFoundError(f"Resale CSV not found: {resale_csv}")
    if not hdb_geojson.exists():
        raise FileNotFoundError(f"HDB GeoJSON not found: {hdb_geojson}")
    if not school_buffer_1km.exists():
        raise FileNotFoundError(f"1km school buffer GeoJSON not found: {school_buffer_1km}")
    if not school_buffer_2km.exists():
        raise FileNotFoundError(f"2km school buffer GeoJSON not found: {school_buffer_2km}")
    if not mall_points_geojson.exists():
        raise FileNotFoundError(f"Mall points GeoJSON not found: {mall_points_geojson}")
    if not mrt_tagged_geojson.exists():
        raise FileNotFoundError(f"MRT tagged GeoJSON not found: {mrt_tagged_geojson}")

    output_csv = (
        Path(args.output_csv)
        if args.output_csv
        else out_dir / "resale_flats_with_school_buffer_counts.csv"
    )
    matched_geojson_out = (
        Path(args.matched_addresses_geojson)
        if args.matched_addresses_geojson
        else out_dir / "resale_address_points_matched_with_school_counts.geojson"
    )
    unmatched_geojson_out = (
        Path(args.unmatched_addresses_geojson)
        if args.unmatched_addresses_geojson
        else out_dir / "resale_address_points_unmatched.geojson"
    )
    point_count_by_postal_out = (
        Path(args.point_count_by_postal_csv)
        if args.point_count_by_postal_csv
        else out_dir / "resale_address_point_count_by_postal_code.csv"
    )

    print("Loading resale transactions and building address points...")
    resale_df, resale_points = load_resale_with_points(resale_csv, geocode_cache_csv)

    print("Loading HDB polygons and matching resale points to polygons...")
    hdb_polygons = ensure_wgs84(gpd.read_file(hdb_geojson))
    matched_points, unmatched_points, matched_polygons, poly_id_col = assign_points_to_hdb_polygons(
        resale_points,
        hdb_polygons,
    )

    print("Loading school buffers and counting polygon intersections...")
    buffer_1km_gdf = load_school_buffer(school_buffer_1km)
    buffer_2km_gdf = load_school_buffer(school_buffer_2km)

    counts_1km = count_school_intersections(matched_polygons, buffer_1km_gdf, poly_id_col, "1km")
    counts_2km = count_school_intersections(matched_polygons, buffer_2km_gdf, poly_id_col, "2km")

    polygon_counts = (
        matched_polygons[[poly_id_col]]
        .drop_duplicates()
        .merge(counts_1km, on=poly_id_col, how="left")
        .merge(counts_2km, on=poly_id_col, how="left")
        .fillna(0)
    )
    for col in [
        "school_count_1km",
        "good_school_count_1km",
        "school_count_2km",
        "good_school_count_2km",
    ]:
        polygon_counts[col] = polygon_counts[col].astype(int)

    print("Loading mall points and computing mall accessibility features...")
    malls_gdf = load_mall_points(mall_points_geojson)
    matched_points = add_mall_access_features(
        matched_points,
        malls_gdf,
        walk_distance_10min_m=args.walk_distance_10min_m,
        network_detour_factor=args.network_detour_factor,
    )
    print("Loading MRT points and computing MRT accessibility features...")
    mrt_gdf = load_mrt_exits_with_lines(mrt_tagged_geojson)
    matched_points = add_mrt_access_features(
        matched_points,
        mrt_gdf,
        walk_distance_10min_m=args.walk_distance_10min_m,
        network_detour_factor=args.network_detour_factor,
    )

    # Map polygon-level counts back to unique resale addresses, then to all transactions.
    point_cols = [poly_id_col, "address_key"]
    point_cols += first_existing(matched_points.columns, ["BLK_NO", "POSTAL_COD", "ST_COD", "ENTITYID"])
    point_cols += first_existing(
        matched_points.columns,
        [
            "nearest_mall_name",
            "nearest_mall_walking_distance_m",
            "malls_within_10min_walk",
            "nearest_mrt_station_name",
            "nearest_mrt_walking_distance_m",
            "mrt_unique_lines_within_10min_walk",
        ],
    )
    address_map = (
        matched_points[point_cols]
        .drop_duplicates(subset=["address_key"], keep="first")
        .merge(polygon_counts, on=poly_id_col, how="left")
    )

    resale_out = resale_df.merge(address_map, on="address_key", how="inner")
    for col in [
        "school_count_1km",
        "good_school_count_1km",
        "school_count_2km",
        "good_school_count_2km",
        "malls_within_10min_walk",
        "mrt_unique_lines_within_10min_walk",
    ]:
        resale_out[col] = resale_out[col].fillna(0).astype(int)
    if "nearest_mall_walking_distance_m" in resale_out.columns:
        resale_out["nearest_mall_walking_distance_m"] = pd.to_numeric(
            resale_out["nearest_mall_walking_distance_m"], errors="coerce"
        )
    if "nearest_mrt_walking_distance_m" in resale_out.columns:
        resale_out["nearest_mrt_walking_distance_m"] = pd.to_numeric(
            resale_out["nearest_mrt_walking_distance_m"], errors="coerce"
        )

    # Save outputs.
    resale_out.to_csv(output_csv, index=False, encoding="utf-8-sig")

    matched_points_out = matched_points.merge(polygon_counts, on=poly_id_col, how="left")
    matched_points_out.to_file(matched_geojson_out, driver="GeoJSON")
    unmatched_points.to_file(unmatched_geojson_out, driver="GeoJSON")

    # Additional summary: number of matched resale address points by polygon postal code.
    if "POSTAL_COD" in matched_points.columns:
        postal_summary = matched_points.copy()
        postal_summary["postal_code"] = postal_summary["POSTAL_COD"].astype(str).str.strip()
        postal_summary = postal_summary[postal_summary["postal_code"].str.len() > 0]
        postal_summary = (
            postal_summary.groupby("postal_code", as_index=False)
            .size()
            .rename(columns={"size": "count"})
            .sort_values(["count", "postal_code"], ascending=[False, True])
        )
    else:
        postal_summary = pd.DataFrame(columns=["postal_code", "count"])
    postal_summary.to_csv(point_count_by_postal_out, index=False, encoding="utf-8-sig")

    print("Done.")
    print(f"Resale rows loaded: {len(resale_df)}")
    print(f"Unique resale address points with geometry: {len(resale_points)}")
    print(f"Matched address points in HDB polygons: {len(matched_points)}")
    print(f"Unmatched address points (outside polygons): {len(unmatched_points)}")
    print(f"Transactions retained (within polygons): {len(resale_out)}")
    print(f"Saved resale dataset: {output_csv}")
    print(f"Saved matched address points: {matched_geojson_out}")
    print(f"Saved unmatched address points: {unmatched_geojson_out}")
    print(f"Saved point-count summary by postal code: {point_count_by_postal_out}")


if __name__ == "__main__":
    main()
