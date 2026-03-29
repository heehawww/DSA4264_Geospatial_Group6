#!/usr/bin/env python
"""Download shopping centre coordinates from Kaggle and plot on an interactive Folium map."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Tuple

import folium
import geopandas as gpd
import kagglehub
import pandas as pd
from folium.plugins import Fullscreen, MarkerCluster, MiniMap


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.to_string().upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def detect_columns(df: pd.DataFrame) -> Tuple[str, str, str]:
    lat_candidates = ["LATITUDE", "latitude", "lat", "Lat", "Latitude"]
    lon_candidates = ["LONGITUDE", "longitude", "lon", "lng", "Lon", "Longitude"]
    name_candidates = ["Mall Name", "mall_name", "mall", "name", "Name"]

    lat_col = next((c for c in lat_candidates if c in df.columns), None)
    lon_col = next((c for c in lon_candidates if c in df.columns), None)
    name_col = next((c for c in name_candidates if c in df.columns), None)

    if lat_col is None or lon_col is None:
        raise ValueError(f"Could not detect lat/lon columns. Available columns: {df.columns.tolist()}")

    if name_col is None:
        numeric = {lat_col, lon_col}
        fallback = [c for c in df.columns if c not in numeric]
        if not fallback:
            raise ValueError("Could not detect a name column")
        name_col = fallback[0]

    return name_col, lat_col, lon_col


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
    return [c for c in preferred if c in ura_gdf.columns]


def load_shopping_dataset(dataset_slug: str, csv_file: Optional[str]) -> pd.DataFrame:
    path = Path(kagglehub.dataset_download(dataset_slug))

    if csv_file:
        target = path / csv_file
        if not target.exists():
            raise FileNotFoundError(f"Specified CSV not found in dataset folder: {target}")
    else:
        csvs = sorted(path.glob("*.csv"))
        if not csvs:
            raise FileNotFoundError(f"No CSV found under: {path}")
        target = csvs[0]

    print(f"Using dataset file: {target}")
    df = pd.read_csv(target)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot shopping centres from Kaggle dataset")
    default_inputs_dir = Path(__file__).resolve().parent / "inputs"
    parser.add_argument(
        "--dataset-slug",
        default="karthikgangula/shopping-mall-coordinates",
        help="Kaggle dataset slug",
    )
    parser.add_argument(
        "--csv-file",
        default=None,
        help="Optional specific CSV filename inside dataset folder",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "outputs"),
        help="Output directory",
    )
    parser.add_argument(
        "--ura-geojson",
        default=str(default_inputs_dir / "MasterPlan2025LandUseLayer.geojson"),
        help="URA master plan polygons for point-in-polygon join",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ura_path = Path(args.ura_geojson)
    if not ura_path.exists():
        raise FileNotFoundError(f"URA GeoJSON not found: {ura_path}")

    df = load_shopping_dataset(args.dataset_slug, args.csv_file)
    name_col, lat_col, lon_col = detect_columns(df)

    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326",
    )
    gdf = ensure_wgs84(gdf)

    # Save normalized point outputs.
    points_out = out_dir / "shopping_centres_points.geojson"
    csv_out = out_dir / "shopping_centres_points.csv"

    norm = gdf[[name_col, lat_col, lon_col, "geometry"]].copy()
    norm = norm.rename(columns={name_col: "shopping_centre_name", lat_col: "latitude", lon_col: "longitude"})
    norm.to_file(points_out, driver="GeoJSON")
    norm.drop(columns=["geometry"]).to_csv(csv_out, index=False, encoding="utf-8-sig")

    # Point-in-polygon join to URA master plan polygons.
    print("Loading URA master plan polygons for spatial join...")
    ura = ensure_wgs84(gpd.read_file(ura_path))
    ura_cols = select_ura_columns(ura)
    ura_subset = ura[ura_cols + ["geometry"]].copy()

    joined = gpd.sjoin(norm, ura_subset, how="left", predicate="within")
    matched = joined[joined["index_right"].notna()].copy()
    unmatched = joined[joined["index_right"].isna()].copy()

    # Attach polygon geometry to each matched shopping centre (1 row per centre).
    matched["index_right"] = matched["index_right"].astype(int)
    polygons_for_match = (
        ura_subset.reset_index()
        .rename(columns={"index": "index_right"})
        [["index_right"] + ura_cols + ["geometry"]]
    )

    joined_points_out = out_dir / "shopping_centres_with_ura_join.geojson"
    joined_csv_out = out_dir / "shopping_centres_with_ura_join.csv"
    boundary_out = out_dir / "shopping_centres_ura_polygons.geojson"
    unmatched_out = out_dir / "shopping_centres_unmatched.csv"

    joined.to_file(joined_points_out, driver="GeoJSON")
    joined.drop(columns=["geometry"]).to_csv(joined_csv_out, index=False, encoding="utf-8-sig")
    unmatched.drop(columns=["geometry"]).to_csv(unmatched_out, index=False, encoding="utf-8-sig")

    boundaries = (
        matched.drop(columns=["geometry"])
        .merge(polygons_for_match, on=["index_right"] + ura_cols, how="left")
    )
    boundaries = gpd.GeoDataFrame(boundaries, geometry="geometry", crs=ura_subset.crs)
    boundaries = boundaries.sort_values("shopping_centre_name").drop_duplicates(subset=["shopping_centre_name"], keep="first")
    boundaries.to_file(boundary_out, driver="GeoJSON")

    # Folium map.
    map_out = out_dir / "shopping_centres_interactive_map.html"
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=11, tiles="CartoDB positron")

    poly_layer = folium.FeatureGroup(name="Shopping centres in URA polygons", show=False)
    pts_layer = folium.FeatureGroup(name="Shopping centres", show=True)
    cluster = MarkerCluster(name="Shopping centre cluster").add_to(pts_layer)

    if len(boundaries) > 0:
        folium.GeoJson(
            boundaries,
            name="Joined URA polygons",
            style_function=lambda _f: {
                "color": "#b15928",
                "weight": 1.1,
                "fillColor": "#fdbf6f",
                "fillOpacity": 0.18,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[c for c in ["shopping_centre_name", "LU_DESC", "OBJECTID"] if c in boundaries.columns],
                aliases=["Shopping centre", "Land-use", "URA ObjectID"],
                localize=True,
                sticky=True,
            ),
        ).add_to(poly_layer)

    for row in norm.itertuples(index=False):
        geom = getattr(row, "geometry", None)
        if geom is None or geom.is_empty:
            continue
        name = getattr(row, "shopping_centre_name", "Shopping centre")
        lat = getattr(row, "latitude", None)
        lon = getattr(row, "longitude", None)
        subset = joined[joined["shopping_centre_name"] == name]
        lu_desc = subset["LU_DESC"].iloc[0] if ("LU_DESC" in subset.columns and len(subset) > 0) else ""
        obj = subset["OBJECTID"].iloc[0] if ("OBJECTID" in subset.columns and len(subset) > 0) else ""

        popup = (
            f"<b>{name}</b><br>"
            f"Lat: {lat:.6f}<br>"
            f"Lon: {lon:.6f}<br>"
            f"Land-use: {lu_desc}<br>"
            f"URA ObjectID: {obj}"
        )
        folium.CircleMarker(
            location=[geom.y, geom.x],
            radius=4,
            color="#7a0177",
            weight=1,
            fill=True,
            fill_color="#c51b8a",
            fill_opacity=0.95,
            popup=folium.Popup(popup, max_width=320),
            tooltip=name,
        ).add_to(cluster)

    poly_layer.add_to(m)
    pts_layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen(position="topright", title="Full Screen", title_cancel="Exit Full Screen").add_to(m)
    MiniMap(toggle_display=True).add_to(m)

    minx, miny, maxx, maxy = ura.total_bounds
    m.fit_bounds([[miny, minx], [maxy, maxx]])
    m.save(str(map_out))

    print("Done.")
    print(f"Shopping centres plotted: {len(norm)}")
    print(f"Saved points GeoJSON: {points_out}")
    print(f"Saved points CSV: {csv_out}")
    print(f"Matched shopping centres: {len(matched)}")
    print(f"Unmatched shopping centres: {len(unmatched)}")
    print(f"Saved joined points GeoJSON: {joined_points_out}")
    print(f"Saved joined CSV: {joined_csv_out}")
    print(f"Saved joined URA polygons: {boundary_out}")
    print(f"Saved unmatched CSV: {unmatched_out}")
    print(f"Saved Folium map: {map_out}")


if __name__ == "__main__":
    main()
