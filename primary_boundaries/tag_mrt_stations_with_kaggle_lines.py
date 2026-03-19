#!/usr/bin/env python
"""Tag MRT exit points with lines from Kaggle station dataset and plot in Folium.

Matching key:
- STATION_NA (LTA GeoJSON) == STATION_NAME_ENGLISH (derived Kaggle field)

The tagged line information is stored as a Python-list-like JSON array in `lines_present`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import folium
import geopandas as gpd
import kagglehub
import pandas as pd
from folium.plugins import Fullscreen, MarkerCluster, MiniMap
from kagglehub import KaggleDatasetAdapter


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.to_string().upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def normalize_station_name(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.upper()
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def derive_station_name_english(station_col: pd.Series, type_col: pd.Series) -> pd.Series:
    return normalize_station_name(station_col) + " " + normalize_station_name(type_col) + " STATION"


def load_kaggle_station_frames(dataset_slug: str, file_paths: List[str]) -> List[pd.DataFrame]:
    frames = []
    for fp in file_paths:
        df = kagglehub.load_dataset(KaggleDatasetAdapter.PANDAS, dataset_slug, fp)
        print(f"Loaded Kaggle file '{fp}' with rows: {len(df)}")
        frames.append(df)
    return frames


def prepare_line_mapping(df_main: pd.DataFrame, df_alt: pd.DataFrame) -> pd.DataFrame:
    # Main format (mrt_lrt_stations.csv)
    a = df_main.copy()
    a["STATION_NAME_ENGLISH"] = derive_station_name_english(
        a["STATION_NAME_ENGLISH"],
        a["TRANSPORT_TYPE"],
    )
    a["LINE_NAME"] = a["LINE_ENGLISH"].astype(str).str.strip()

    # Alternate format (mrt_lrt_stations_2025-01-14.csv)
    b = df_alt.copy()
    b["STATION_NAME_ENGLISH"] = derive_station_name_english(
        b["station_name"],
        b["type"],
    )
    b["LINE_NAME"] = b["line"].astype(str).str.strip()

    combined = pd.concat(
        [a[["STATION_NAME_ENGLISH", "LINE_NAME"]], b[["STATION_NAME_ENGLISH", "LINE_NAME"]]],
        ignore_index=True,
    )

    mapping = (
        combined.groupby("STATION_NAME_ENGLISH", as_index=False)
        .agg(lines_present=("LINE_NAME", lambda s: sorted(set(x for x in s if pd.notna(x) and str(x).strip()))))
    )
    mapping["line_count"] = mapping["lines_present"].apply(len)
    return mapping


def write_geojson_with_list_properties(gdf: gpd.GeoDataFrame, path: Path) -> None:
    features = []
    for _, row in gdf.iterrows():
        props = {k: row[k] for k in gdf.columns if k != "geometry"}

        # Ensure lines_present remains a real JSON list in output.
        if "lines_present" in props and isinstance(props["lines_present"], str):
            try:
                props["lines_present"] = json.loads(props["lines_present"])
            except Exception:
                pass

        geom = row.geometry
        feature = {
            "type": "Feature",
            "properties": props,
            "geometry": None if geom is None or geom.is_empty else geom.__geo_interface__,
        }
        features.append(feature)

    fc = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tag MRT exits with line information from Kaggle")
    parser.add_argument(
        "--mrt-exit-geojson",
        default=r"C:\Users\User\Downloads\LTAMRTStationExitGEOJSON (1).geojson",
        help="LTA MRT exit GeoJSON",
    )
    parser.add_argument(
        "--dataset-slug",
        default="lzytim/full-list-of-mrt-and-lrt-stations-in-singapore",
        help="Kaggle dataset slug",
    )
    parser.add_argument(
        "--main-file-path",
        default="mrt_lrt_stations.csv",
        help="Kaggle file path for main MRT dataset",
    )
    parser.add_argument(
        "--alt-file-path",
        default="mrt_lrt_stations_2025-01-14.csv",
        help="Kaggle file path for alternate MRT dataset",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "outputs"),
        help="Output directory",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mrt_path = Path(args.mrt_exit_geojson)
    if not mrt_path.exists():
        raise FileNotFoundError(f"MRT exit GeoJSON not found: {mrt_path}")

    print("Loading MRT exit points...")
    mrt = ensure_wgs84(gpd.read_file(mrt_path))
    if "STATION_NA" not in mrt.columns:
        raise ValueError("Expected STATION_NA in MRT exit GeoJSON")

    print("Loading Kaggle MRT datasets...")
    df_main, df_alt = load_kaggle_station_frames(
        args.dataset_slug,
        [args.main_file_path, args.alt_file_path],
    )

    line_map = prepare_line_mapping(df_main, df_alt)

    tagged = mrt.copy()
    tagged["STATION_NA"] = normalize_station_name(tagged["STATION_NA"])
    tagged = tagged.merge(line_map, left_on="STATION_NA", right_on="STATION_NAME_ENGLISH", how="left")

    tagged["lines_present"] = tagged["lines_present"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    tagged["line_count"] = tagged["lines_present"].apply(len)
    tagged["lines_present_json"] = tagged["lines_present"].apply(lambda x: json.dumps(x, ensure_ascii=False))
    tagged["is_tagged"] = tagged["line_count"] > 0

    # Save tagged outputs.
    tagged_csv = out_dir / "mrt_exits_tagged_with_lines.csv"
    tagged_geojson = out_dir / "mrt_exits_tagged_with_lines.geojson"

    tagged_no_geom = tagged.drop(columns=["geometry"]).copy()
    tagged_no_geom.to_csv(tagged_csv, index=False, encoding="utf-8-sig")
    write_geojson_with_list_properties(tagged, tagged_geojson)

    # Folium map.
    map_out = out_dir / "mrt_exits_tagged_with_lines_map.html"
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=11, tiles="CartoDB positron")

    tagged_layer = folium.FeatureGroup(name="Tagged MRT/LRT exits", show=True)
    untagged_layer = folium.FeatureGroup(name="Unmatched exits", show=True)

    tagged_cluster = MarkerCluster(name="Tagged exits").add_to(tagged_layer)
    untagged_cluster = MarkerCluster(name="Unmatched exits").add_to(untagged_layer)

    for row in tagged.itertuples(index=False):
        geom = getattr(row, "geometry", None)
        if geom is None or geom.is_empty:
            continue

        station = getattr(row, "STATION_NA", "Unknown station")
        exit_code = getattr(row, "EXIT_CODE", "")
        lines = getattr(row, "lines_present", [])
        line_count = int(getattr(row, "line_count", 0))
        is_tagged = bool(getattr(row, "is_tagged", False))

        lines_text = ", ".join(lines) if lines else "No match"
        popup = (
            f"<b>{station}</b><br>"
            f"Exit: {exit_code}<br>"
            f"Lines ({line_count}): {lines_text}"
        )

        color = "#006d2c" if is_tagged else "#cb181d"
        marker = folium.CircleMarker(
            location=[geom.y, geom.x],
            radius=4 if is_tagged else 5,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.95,
            popup=folium.Popup(popup, max_width=360),
            tooltip=station,
        )

        if is_tagged:
            marker.add_to(tagged_cluster)
        else:
            marker.add_to(untagged_cluster)

    tagged_layer.add_to(m)
    untagged_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen(position="topright", title="Full Screen", title_cancel="Exit Full Screen").add_to(m)
    MiniMap(toggle_display=True).add_to(m)

    minx, miny, maxx, maxy = tagged.total_bounds
    m.fit_bounds([[miny, minx], [maxy, maxx]])
    m.save(str(map_out))

    matched = int(tagged["is_tagged"].sum())
    unmatched = int((~tagged["is_tagged"]).sum())

    print("Done.")
    print(f"Tagged exits: {matched}")
    print(f"Unmatched exits: {unmatched}")
    print(f"Saved tagged CSV: {tagged_csv}")
    print(f"Saved tagged GeoJSON: {tagged_geojson}")
    print(f"Saved Folium map: {map_out}")


if __name__ == "__main__":
    main()
