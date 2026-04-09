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
import inspect
import json
import os
import time
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import networkx as nx
import pandas as pd
import requests
from scipy.spatial import cKDTree
from shapely.geometry import box

try:
    import osmnx as ox
except Exception:  # pragma: no cover
    ox = None


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.to_string().upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def first_existing(columns: Iterable[str], candidates: list[str]) -> list[str]:
    cols = set(columns)
    return [c for c in candidates if c in cols]


def load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from a local .env file."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


class OneMapRoutingClient:
    """OneMap walking-distance client without disk cache."""

    API_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"

    def __init__(
        self,
        api_key: str,
        request_sleep_seconds: float = 0.0,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key
        self.request_sleep_seconds = max(0.0, float(request_sleep_seconds))
        self.timeout_seconds = int(timeout_seconds)
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.session = requests.Session()
        self.session.headers.update({"Authorization": self.api_key})

    @staticmethod
    def _extract_distance_m(payload: object) -> float | None:
        if not isinstance(payload, dict):
            return None

        route_summary = payload.get("route_summary")
        if isinstance(route_summary, dict):
            for key in ("total_distance", "distance", "totalDistance"):
                value = route_summary.get(key)
                if value is not None:
                    try:
                        distance_m = float(value)
                        if distance_m >= 0:
                            return distance_m
                    except (TypeError, ValueError):
                        pass

        for key in ("total_distance", "distance", "totalDistance"):
            value = payload.get(key)
            if value is not None:
                try:
                    distance_m = float(value)
                    if distance_m >= 0:
                        return distance_m
                except (TypeError, ValueError):
                    pass

        return None

    def _fetch_walking_distance(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> float | None:
        o_lat, o_lon = origin
        d_lat, d_lon = destination
        params = {
            "routeType": "walk",
            "start": f"{o_lat:.7f},{o_lon:.7f}",
            "end": f"{d_lat:.7f},{d_lon:.7f}",
        }

        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.session.get(self.API_URL, params=params, timeout=self.timeout_seconds)
                if resp.status_code in {429, 500, 502, 503, 504} and attempt <= (self.max_retries + 1):
                    if self.retry_backoff_seconds > 0:
                        time.sleep(self.retry_backoff_seconds * (attempt - 1))
                    continue
                resp.raise_for_status()
                payload = resp.json()
                return self._extract_distance_m(payload)
            except requests.RequestException:
                if attempt <= (self.max_retries + 1):
                    if self.retry_backoff_seconds > 0:
                        time.sleep(self.retry_backoff_seconds * (attempt - 1))
                    continue
                raise

    def get_walking_distances(
        self,
        origin: tuple[float, float],
        destinations: list[tuple[float, float]],
    ) -> list[float | None]:
        if not destinations:
            return []

        out: list[float | None] = [None] * len(destinations)
        for idx, destination in enumerate(destinations):
            dist = self._fetch_walking_distance(origin, destination)
            out[idx] = dist
            if self.request_sleep_seconds > 0:
                time.sleep(self.request_sleep_seconds)

        return out


def build_osmnx_graph(
    matched_points: gpd.GeoDataFrame,
    malls_gdf: gpd.GeoDataFrame,
    mrt_gdf: gpd.GeoDataFrame,
    network_type: str = "walk",
    buffer_m: float = 1200.0,
) -> nx.MultiDiGraph:
    if ox is None:
        raise ImportError("osmnx is not installed. Install osmnx to use distance-provider=osmnx.")
    # Disable OSMnx HTTP caching so this script does not create local cache files.
    ox.settings.use_cache = False

    layers = [ensure_wgs84(matched_points), ensure_wgs84(malls_gdf), ensure_wgs84(mrt_gdf)]
    combined = pd.concat(layers, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    combined = combined[combined.geometry.notna() & (~combined.geometry.is_empty)].copy()
    combined = combined[combined.geometry.geom_type == "Point"].copy()
    if combined.empty:
        raise ValueError("Cannot build OSMnx graph: empty geometry layers.")

    projected = combined.to_crs("EPSG:3414")
    minx, miny, maxx, maxy = projected.total_bounds
    minx -= float(buffer_m)
    miny -= float(buffer_m)
    maxx += float(buffer_m)
    maxy += float(buffer_m)

    bbox_proj = gpd.GeoDataFrame(
        {"geometry": [box(minx, miny, maxx, maxy)]},
        geometry="geometry",
        crs="EPSG:3414",
    )
    bbox_wgs = bbox_proj.to_crs("EPSG:4326")
    west, south, east, north = bbox_wgs.total_bounds

    north = float(north)
    south = float(south)
    east = float(east)
    west = float(west)

    if not np.isfinite([west, south, east, north]).all():
        raise ValueError(
            f"Invalid OSMnx bbox values (NaN/Inf): west={west}, south={south}, east={east}, north={north}"
        )
    if east <= west or north <= south:
        raise ValueError(
            f"Invalid OSMnx bbox ordering: west={west}, south={south}, east={east}, north={north}"
        )

    # OSMnx v1 and v2 use different graph_from_bbox signatures.
    sig_params = set(inspect.signature(ox.graph_from_bbox).parameters.keys())
    if "bbox" in sig_params:
        # OSMnx v2 expects bbox ordering as (left, bottom, right, top).
        try:
            G = ox.graph_from_bbox(
                bbox=(west, south, east, north),
                network_type=network_type,
                simplify=True,
            )
        except TypeError:
            G = ox.graph_from_bbox(
                north=north,
                south=south,
                east=east,
                west=west,
                network_type=network_type,
                simplify=True,
            )
    else:
        # OSMnx v1 signature.
        try:
            G = ox.graph_from_bbox(
                north=north,
                south=south,
                east=east,
                west=west,
                network_type=network_type,
                simplify=True,
            )
        except TypeError:
            G = ox.graph_from_bbox(
                bbox=(west, south, east, north),
                network_type=network_type,
                simplify=True,
            )
    return G


def nearest_nodes_for_gdf(graph: nx.MultiDiGraph, gdf_wgs84: gpd.GeoDataFrame) -> list[int]:
    if ox is None:
        raise ImportError("osmnx is not installed. Install osmnx to use distance-provider=osmnx.")
    if gdf_wgs84.empty:
        return []
    xs = gdf_wgs84.geometry.x.to_numpy()
    ys = gdf_wgs84.geometry.y.to_numpy()
    nodes = ox.distance.nearest_nodes(graph, X=xs, Y=ys)
    if isinstance(nodes, (list, tuple)):
        return [int(n) for n in nodes]
    return [int(n) for n in np.array(nodes).tolist()]


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
    distance_provider: str = "onemap",
    onemap_client: OneMapRoutingClient | None = None,
    onemap_nearest_candidate_k: int = 25,
    osmnx_graph: nx.MultiDiGraph | None = None,
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

    pts_wgs = out.to_crs("EPSG:4326").copy()
    pts_proj = out.to_crs("EPSG:3414").copy()
    malls_wgs = malls_gdf.to_crs("EPSG:4326").copy()
    malls_proj = malls_gdf.to_crs("EPSG:3414").copy()

    mall_xy = np.column_stack([malls_proj.geometry.x.to_numpy(), malls_proj.geometry.y.to_numpy()])
    mall_latlon = np.column_stack([malls_wgs.geometry.y.to_numpy(), malls_wgs.geometry.x.to_numpy()])
    mall_names = malls_wgs["shopping_centre_name"].astype(str).to_numpy()

    point_xy = np.column_stack([pts_proj.geometry.x.to_numpy(), pts_proj.geometry.y.to_numpy()])
    point_latlon = np.column_stack([pts_wgs.geometry.y.to_numpy(), pts_wgs.geometry.x.to_numpy()])

    tree = cKDTree(mall_xy)
    nearest_euclid, nearest_idx = tree.query(point_xy, k=1)

    provider = distance_provider.lower()

    if provider == "onemap":
        if onemap_client is None:
            raise ValueError("onemap_client is required when distance_provider='onemap'")

        nearest_names = []
        nearest_walk_dist = []
        within_counts = []

        radius_for_count = float(walk_distance_10min_m)
        for i, (origin_xy, origin_ll) in enumerate(zip(point_xy, point_latlon)):
            # Candidate set for 10-minute count: exact by lower-bound logic (walk >= euclidean).
            count_candidates = tree.query_ball_point(origin_xy, r=radius_for_count)
            count_destinations = [tuple(mall_latlon[idx]) for idx in count_candidates]
            count_distances = onemap_client.get_walking_distances(tuple(origin_ll), count_destinations)
            within_count = sum(
                1 for d in count_distances if d is not None and d <= float(walk_distance_10min_m)
            )
            within_counts.append(int(within_count))

            # Candidate set for nearest mall: top-k by euclidean to control API calls.
            euclid_d = np.sqrt(((mall_xy - origin_xy) ** 2).sum(axis=1))
            sort_idx = np.argsort(euclid_d)
            if onemap_nearest_candidate_k and onemap_nearest_candidate_k > 0:
                sort_idx = sort_idx[: int(onemap_nearest_candidate_k)]

            near_destinations = [tuple(mall_latlon[idx]) for idx in sort_idx]
            near_distances = onemap_client.get_walking_distances(tuple(origin_ll), near_destinations)

            best_idx = None
            best_dist = None
            for idx_local, dist in enumerate(near_distances):
                if dist is None:
                    continue
                if best_dist is None or dist < best_dist:
                    best_dist = float(dist)
                    best_idx = idx_local

            if best_idx is None:
                # Fallback if no OneMap route returned.
                fallback_idx = int(nearest_idx[i])
                nearest_names.append(str(mall_names[fallback_idx]))
                nearest_walk_dist.append(float(nearest_euclid[i] * network_detour_factor))
            else:
                chosen_global_idx = int(sort_idx[best_idx])
                nearest_names.append(str(mall_names[chosen_global_idx]))
                nearest_walk_dist.append(float(best_dist))

        out["nearest_mall_name"] = nearest_names
        out["nearest_mall_walking_distance_m"] = nearest_walk_dist
        out["malls_within_10min_walk"] = within_counts
    elif provider == "osmnx":
        if osmnx_graph is None:
            raise ValueError("osmnx_graph is required when distance_provider='osmnx'")

        point_nodes = nearest_nodes_for_gdf(osmnx_graph, pts_wgs)
        mall_nodes = nearest_nodes_for_gdf(osmnx_graph, malls_wgs)

        point_node_to_rows: dict[int, list[int]] = {}
        for row_idx, node in enumerate(point_nodes):
            point_node_to_rows.setdefault(int(node), []).append(int(row_idx))

        # Nearest mall distance + nearest mall name from multi-source Dijkstra.
        mall_node_to_name: dict[int, str] = {}
        for n, name in zip(mall_nodes, mall_names):
            mall_node_to_name.setdefault(int(n), str(name))
        source_nodes = list(mall_node_to_name.keys())

        nearest_dist = {}
        nearest_paths = {}
        if source_nodes:
            nearest_dist, nearest_paths = nx.multi_source_dijkstra(
                osmnx_graph,
                sources=source_nodes,
                weight="length",
            )

        nearest_names = []
        nearest_walk_dist = []
        for idx, node in enumerate(point_nodes):
            node = int(node)
            if node in nearest_dist and node in nearest_paths and len(nearest_paths[node]) > 0:
                src_node = int(nearest_paths[node][0])
                nearest_names.append(mall_node_to_name.get(src_node, str(mall_names[int(nearest_idx[idx])])))
                nearest_walk_dist.append(float(nearest_dist[node]))
            else:
                # disconnected fallback
                nearest_names.append(str(mall_names[int(nearest_idx[idx])]))
                nearest_walk_dist.append(float(nearest_euclid[idx] * network_detour_factor))

        # Count malls within 10-min walk by network distance.
        within_counts = [0] * len(point_nodes)
        for m_node in mall_nodes:
            m_node = int(m_node)
            lengths = nx.single_source_dijkstra_path_length(
                osmnx_graph,
                source=m_node,
                cutoff=float(walk_distance_10min_m),
                weight="length",
            )
            for node_hit in lengths.keys():
                rows = point_node_to_rows.get(int(node_hit))
                if rows:
                    for r in rows:
                        within_counts[r] += 1

        out["nearest_mall_name"] = nearest_names
        out["nearest_mall_walking_distance_m"] = nearest_walk_dist
        out["malls_within_10min_walk"] = within_counts
    else:
        # Euclidean fallback mode.
        nearest_dist_walk_m = nearest_euclid * network_detour_factor
        nearest_names = malls_proj.iloc[nearest_idx]["shopping_centre_name"].to_numpy()
        euclidean_radius_m = walk_distance_10min_m / network_detour_factor
        nearby_idx_lists = tree.query_ball_point(point_xy, r=euclidean_radius_m)
        nearby_counts = [len(idxs) for idxs in nearby_idx_lists]

        out["nearest_mall_name"] = nearest_names
        out["nearest_mall_walking_distance_m"] = nearest_dist_walk_m
        out["malls_within_10min_walk"] = nearby_counts

    out["nearest_mall_walking_distance_m"] = pd.to_numeric(
        out["nearest_mall_walking_distance_m"], errors="coerce"
    ).astype(float)
    out["malls_within_10min_walk"] = pd.to_numeric(
        out["malls_within_10min_walk"], errors="coerce"
    ).fillna(0).astype(int)
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
    distance_provider: str = "onemap",
    onemap_client: OneMapRoutingClient | None = None,
    onemap_nearest_candidate_k: int = 40,
    osmnx_graph: nx.MultiDiGraph | None = None,
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

    pts_wgs = out.to_crs("EPSG:4326").copy()
    pts_proj = out.to_crs("EPSG:3414").copy()
    mrt_wgs = mrt_gdf.to_crs("EPSG:4326").copy()
    mrt_proj = mrt_gdf.to_crs("EPSG:3414").copy()

    point_xy = np.column_stack([pts_proj.geometry.x.to_numpy(), pts_proj.geometry.y.to_numpy()])
    point_latlon = np.column_stack([pts_wgs.geometry.y.to_numpy(), pts_wgs.geometry.x.to_numpy()])
    mrt_xy = np.column_stack([mrt_proj.geometry.x.to_numpy(), mrt_proj.geometry.y.to_numpy()])
    mrt_latlon = np.column_stack([mrt_wgs.geometry.y.to_numpy(), mrt_wgs.geometry.x.to_numpy()])
    station_values = mrt_wgs["__station_name"].astype(str).tolist()
    lines_values = mrt_wgs["__lines_list"].tolist()

    tree = cKDTree(mrt_xy)
    nearest_euclid, nearest_idx = tree.query(point_xy, k=1)

    provider = distance_provider.lower()

    if provider == "onemap":
        if onemap_client is None:
            raise ValueError("onemap_client is required when distance_provider='onemap'")

        nearest_station_names = []
        nearest_station_distances = []
        unique_line_counts = []
        radius_for_count = float(walk_distance_10min_m)

        for i, (origin_xy, origin_ll) in enumerate(zip(point_xy, point_latlon)):
            # Count of unique lines within 10-min walk:
            # first candidate exits by euclidean lower bound, then true walking filter via OneMap.
            count_candidates = tree.query_ball_point(origin_xy, r=radius_for_count)
            count_destinations = [tuple(mrt_latlon[idx]) for idx in count_candidates]
            count_distances = onemap_client.get_walking_distances(tuple(origin_ll), count_destinations)

            station_lines_map: dict[str, set[str]] = {}
            for idx_local, dist in enumerate(count_distances):
                if dist is None or dist > float(walk_distance_10min_m):
                    continue
                idx_global = count_candidates[idx_local]
                st = station_values[idx_global]
                if st not in station_lines_map:
                    station_lines_map[st] = set()
                for line_name in lines_values[idx_global]:
                    if line_name:
                        station_lines_map[st].add(str(line_name).strip())

            merged_lines = set()
            for st in station_lines_map:
                merged_lines.update(station_lines_map[st])
            unique_line_counts.append(int(len(merged_lines)))

            # Nearest station by walking distance (approximate search budget via top-k exits by euclidean).
            euclid_d = np.sqrt(((mrt_xy - origin_xy) ** 2).sum(axis=1))
            sort_idx = np.argsort(euclid_d)
            if onemap_nearest_candidate_k and onemap_nearest_candidate_k > 0:
                sort_idx = sort_idx[: int(onemap_nearest_candidate_k)]
            near_destinations = [tuple(mrt_latlon[idx]) for idx in sort_idx]
            near_distances = onemap_client.get_walking_distances(tuple(origin_ll), near_destinations)

            best_station = None
            best_dist = None
            for idx_local, dist in enumerate(near_distances):
                if dist is None:
                    continue
                idx_global = int(sort_idx[idx_local])
                st = station_values[idx_global]
                if best_dist is None or dist < best_dist:
                    best_dist = float(dist)
                    best_station = st

            if best_station is None:
                fallback_idx = int(nearest_idx[i])
                nearest_station_names.append(str(station_values[fallback_idx]))
                nearest_station_distances.append(float(nearest_euclid[i] * network_detour_factor))
            else:
                nearest_station_names.append(str(best_station))
                nearest_station_distances.append(float(best_dist))

        out["nearest_mrt_station_name"] = nearest_station_names
        out["nearest_mrt_walking_distance_m"] = nearest_station_distances
        out["mrt_unique_lines_within_10min_walk"] = unique_line_counts
    elif provider == "osmnx":
        if osmnx_graph is None:
            raise ValueError("osmnx_graph is required when distance_provider='osmnx'")

        point_nodes = nearest_nodes_for_gdf(osmnx_graph, pts_wgs)
        mrt_nodes = nearest_nodes_for_gdf(osmnx_graph, mrt_wgs)

        point_node_to_rows: dict[int, list[int]] = {}
        for row_idx, node in enumerate(point_nodes):
            point_node_to_rows.setdefault(int(node), []).append(int(row_idx))

        # Nearest MRT station using all exit nodes as sources.
        source_to_station: dict[int, str] = {}
        for n, st in zip(mrt_nodes, station_values):
            source_to_station.setdefault(int(n), str(st))
        source_nodes = list(source_to_station.keys())

        nearest_dist = {}
        nearest_paths = {}
        if source_nodes:
            nearest_dist, nearest_paths = nx.multi_source_dijkstra(
                osmnx_graph,
                sources=source_nodes,
                weight="length",
            )

        nearest_station_names = []
        nearest_station_dists = []
        for idx, n in enumerate(point_nodes):
            n = int(n)
            if n in nearest_dist and n in nearest_paths and len(nearest_paths[n]) > 0:
                src = int(nearest_paths[n][0])
                nearest_station_names.append(source_to_station.get(src, str(station_values[int(nearest_idx[idx])])))
                nearest_station_dists.append(float(nearest_dist[n]))
            else:
                nearest_station_names.append(str(station_values[int(nearest_idx[idx])]))
                nearest_station_dists.append(float(nearest_euclid[idx] * network_detour_factor))

        # Unique MRT lines within 10-min walking distance.
        station_to_nodes: dict[str, set[int]] = {}
        station_to_lines: dict[str, set[str]] = {}
        for st, node, lines in zip(station_values, mrt_nodes, lines_values):
            st = str(st)
            station_to_nodes.setdefault(st, set()).add(int(node))
            station_to_lines.setdefault(st, set())
            for ln in lines:
                if ln:
                    station_to_lines[st].add(str(ln).strip())

        row_line_sets = [set() for _ in range(len(point_nodes))]
        for st, nodes in station_to_nodes.items():
            if not nodes:
                continue
            lengths = nx.multi_source_dijkstra_path_length(
                osmnx_graph,
                sources=list(nodes),
                cutoff=float(walk_distance_10min_m),
                weight="length",
            )
            st_lines = station_to_lines.get(st, set())
            if not st_lines:
                continue
            for node_hit in lengths.keys():
                rows = point_node_to_rows.get(int(node_hit))
                if rows:
                    for r in rows:
                        row_line_sets[r].update(st_lines)

        out["nearest_mrt_station_name"] = nearest_station_names
        out["nearest_mrt_walking_distance_m"] = nearest_station_dists
        out["mrt_unique_lines_within_10min_walk"] = [len(s) for s in row_line_sets]
    else:
        nearest_dist_walk_m = nearest_euclid * network_detour_factor
        nearest_station_names = mrt_proj.iloc[nearest_idx]["__station_name"].to_numpy()
        out["nearest_mrt_station_name"] = nearest_station_names
        out["nearest_mrt_walking_distance_m"] = nearest_dist_walk_m.astype(float)

        euclidean_radius_m = walk_distance_10min_m / network_detour_factor
        nearby_idx_lists = tree.query_ball_point(point_xy, r=euclidean_radius_m)

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
            unique_lines = set()
            for station_lines in station_lines_map.values():
                unique_lines.update(station_lines)
            unique_line_counts.append(len(unique_lines))

        out["mrt_unique_lines_within_10min_walk"] = pd.Series(unique_line_counts, index=out.index).astype(int)

    out["nearest_mrt_walking_distance_m"] = pd.to_numeric(
        out["nearest_mrt_walking_distance_m"], errors="coerce"
    ).astype(float)
    out["mrt_unique_lines_within_10min_walk"] = pd.to_numeric(
        out["mrt_unique_lines_within_10min_walk"], errors="coerce"
    ).fillna(0).astype(int)
    return out


def main() -> None:
    load_env_file(Path(__file__).resolve().parent / ".env")
    load_env_file(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(
        description="Create resale-flat dataset with school counts from 1km/2km polygon-buffer intersections"
    )
    default_inputs_dir = Path(__file__).resolve().parent / "inputs"
    parser.add_argument(
        "--resale-csv",
        default=str(default_inputs_dir / "ResaleflatpricesbasedonregistrationdatefromJan2017onwards.csv"),
        help="Resale flat CSV path",
    )
    parser.add_argument(
        "--hdb-geojson",
        default=str(default_inputs_dir / "HDBExistingBuilding.geojson"),
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
        "--distance-provider",
        choices=["onemap", "osmnx", "euclidean"],
        default="onemap",
        help="Distance provider for mall/MRT accessibility features",
    )
    parser.add_argument(
        "--onemap-api-key",
        default=os.getenv("ONEMAP_API_KEY"),
        help="OneMap API key (or set ONEMAP_API_KEY in environment/.env)",
    )
    parser.add_argument(
        "--onemap-request-sleep-seconds",
        type=float,
        default=0.0,
        help="Optional delay between OneMap API requests",
    )
    parser.add_argument(
        "--onemap-timeout-seconds",
        type=int,
        default=30,
        help="HTTP timeout for OneMap API requests",
    )
    parser.add_argument(
        "--onemap-nearest-candidate-k",
        type=int,
        default=25,
        help="Top-K nearest euclidean candidates to evaluate via OneMap for nearest-distance fields",
    )
    parser.add_argument(
        "--osmnx-network-type",
        default="walk",
        help="OSMnx network type (typically 'walk')",
    )
    parser.add_argument(
        "--osmnx-buffer-m",
        type=float,
        default=1200.0,
        help="Meters to buffer around data bounds when downloading OSM graph",
    )
    parser.add_argument(
        "--network-detour-factor",
        type=float,
        default=1.0,
        help="Used only in euclidean fallback mode",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "outputs" / "onemap"),
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
    if args.distance_provider == "osmnx" and ox is None:
        raise ImportError("osmnx is not installed. Run `pip install osmnx`.")
    if args.distance_provider == "onemap" and not args.onemap_api_key:
        raise ValueError(
            "OneMap distance provider selected but no API key was provided. "
            "Set ONEMAP_API_KEY (env/.env) or pass --onemap-api-key."
        )

    onemap_client = None
    osmnx_graph = None
    if args.distance_provider == "onemap":
        onemap_client = OneMapRoutingClient(
            api_key=str(args.onemap_api_key),
            request_sleep_seconds=float(args.onemap_request_sleep_seconds),
            timeout_seconds=int(args.onemap_timeout_seconds),
        )

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
    if args.distance_provider == "osmnx":
        print("Building OSMnx walking graph (cache disabled)...")
        mrt_seed = load_mrt_exits_with_lines(mrt_tagged_geojson)
        osmnx_graph = build_osmnx_graph(
            matched_points=matched_points,
            malls_gdf=malls_gdf,
            mrt_gdf=mrt_seed,
            network_type=str(args.osmnx_network_type),
            buffer_m=float(args.osmnx_buffer_m),
        )
    else:
        mrt_seed = None

    matched_points = add_mall_access_features(
        matched_points,
        malls_gdf,
        walk_distance_10min_m=args.walk_distance_10min_m,
        network_detour_factor=args.network_detour_factor,
        distance_provider=args.distance_provider,
        onemap_client=onemap_client,
        onemap_nearest_candidate_k=args.onemap_nearest_candidate_k,
        osmnx_graph=osmnx_graph,
    )
    print("Loading MRT points and computing MRT accessibility features...")
    mrt_gdf = mrt_seed if mrt_seed is not None else load_mrt_exits_with_lines(mrt_tagged_geojson)
    matched_points = add_mrt_access_features(
        matched_points,
        mrt_gdf,
        walk_distance_10min_m=args.walk_distance_10min_m,
        network_detour_factor=args.network_detour_factor,
        distance_provider=args.distance_provider,
        onemap_client=onemap_client,
        onemap_nearest_candidate_k=max(int(args.onemap_nearest_candidate_k), 40),
        osmnx_graph=osmnx_graph,
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
