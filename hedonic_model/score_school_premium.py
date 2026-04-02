#!/usr/bin/env python3
"""Score HDB resale transactions with model-based good-school premiums."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

try:
    from hedonic_model.train_hedonic_model import (
        NUMERIC_FEATURES,
        PREDICTIVE_CATEGORICAL_FEATURES,
        engineer_features,
        fit_predictive_model,
    )
except ModuleNotFoundError:
    from train_hedonic_model import (  # type: ignore
        NUMERIC_FEATURES,
        PREDICTIVE_CATEGORICAL_FEATURES,
        engineer_features,
        fit_predictive_model,
    )


EXPORT_COLUMNS = [
    "month",
    "town",
    "flat_type",
    "block",
    "street_name",
    "storey_range",
    "flat_model",
    "floor_area_sqm",
    "lease_commence_date",
    "remaining_lease",
    "resale_price",
    "address_key",
    "school_count_1km",
    "good_school_count_1km",
    "school_count_2km",
    "good_school_count_2km",
    "predicted_price",
    "predicted_price_without_good_school_1km",
    "estimated_good_school_1km_premium_sgd",
    "estimated_good_school_1km_premium_pct",
]


def load_points(points_path: Path) -> gpd.GeoDataFrame:
    points = gpd.read_file(points_path)
    if points.crs is None:
        points = points.set_crs(4326)
    points = points.to_crs(4326)
    points = (
        points.sort_values("__point_id" if "__point_id" in points.columns else "address_key")
        .drop_duplicates(subset=["address_key"], keep="first")
        .copy()
    )
    keep_columns = ["address_key", "geometry"]
    for optional in ("latitude", "longitude"):
        if optional in points.columns:
            keep_columns.append(optional)
    return points[keep_columns]


def fit_full_predictive_model(model_df: pd.DataFrame):
    return fit_predictive_model(model_df, model_df)[0]


def build_counterfactual_inputs(model_df: pd.DataFrame) -> pd.DataFrame:
    counterfactual = model_df[NUMERIC_FEATURES + PREDICTIVE_CATEGORICAL_FEATURES].copy()
    counterfactual["good_school_count_1km"] = 0
    counterfactual["good_school_within_1km"] = 0
    return counterfactual


def score_premiums(raw_df: pd.DataFrame, model_df: pd.DataFrame, model) -> pd.DataFrame:
    X_actual = model_df[NUMERIC_FEATURES + PREDICTIVE_CATEGORICAL_FEATURES]
    X_counterfactual = build_counterfactual_inputs(model_df)

    predicted_price = np.exp(model.predict(X_actual))
    predicted_counterfactual = np.exp(model.predict(X_counterfactual))
    premium_sgd = predicted_price - predicted_counterfactual
    premium_pct = np.divide(
        premium_sgd,
        predicted_counterfactual,
        out=np.zeros_like(premium_sgd),
        where=predicted_counterfactual > 0,
    )

    scored = raw_df.loc[model_df.index, EXPORT_COLUMNS[:-4]].copy()
    scored["predicted_price"] = predicted_price
    scored["predicted_price_without_good_school_1km"] = predicted_counterfactual
    scored["estimated_good_school_1km_premium_sgd"] = premium_sgd
    scored["estimated_good_school_1km_premium_pct"] = premium_pct
    return scored


def write_geojson(scored: pd.DataFrame, points: gpd.GeoDataFrame, output_path: Path) -> None:
    output_gdf = points.merge(scored, on="address_key", how="inner", validate="1:m")
    geojson = json.loads(output_gdf.to_json(drop_id=True))
    output_path.write_text(json.dumps(geojson))


def main() -> None:
    parser = argparse.ArgumentParser(description="Score resale flats with estimated good-school premiums")
    parser.add_argument(
        "--input-csv",
        default="walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv",
        help="Input preprocessed feature CSV",
    )
    parser.add_argument(
        "--points-geojson",
        default="primary_boundaries/outputs/resale_address_points_matched_with_school_counts.geojson",
        help="GeoJSON with geocoded resale address points",
    )
    parser.add_argument(
        "--output-dir",
        default="hedonic_model/scored_outputs",
        help="Directory for scored CSV and GeoJSON outputs",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    points_geojson = Path(args.points_geojson)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")
    if not points_geojson.exists():
        raise FileNotFoundError(f"Points GeoJSON not found: {points_geojson}")

    print(f"Loading {input_csv} ...")
    raw_df = pd.read_csv(input_csv)
    model_df = engineer_features(raw_df)

    print("Training predictive model on all rows for scoring...")
    predictive_model = fit_full_predictive_model(model_df)

    print("Scoring premiums...")
    scored = score_premiums(raw_df, model_df, predictive_model)

    csv_output = output_dir / "flat_school_premiums.csv"
    scored.to_csv(csv_output, index=False)

    print("Joining geocoded address points and exporting GeoJSON...")
    points = load_points(points_geojson)
    geojson_output = output_dir / "flat_school_premiums.geojson"
    write_geojson(scored, points, geojson_output)

    summary = {
        "rows_scored": int(len(scored)),
        "unique_addresses_scored": int(scored["address_key"].nunique()),
        "mean_premium_sgd": float(scored["estimated_good_school_1km_premium_sgd"].mean()),
        "median_premium_sgd": float(scored["estimated_good_school_1km_premium_sgd"].median()),
        "mean_premium_pct": float(scored["estimated_good_school_1km_premium_pct"].mean()),
        "share_with_positive_premium": float(
            (scored["estimated_good_school_1km_premium_sgd"] > 0).mean()
        ),
    }
    (output_dir / "scoring_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"Wrote {csv_output}")
    print(f"Wrote {geojson_output}")


if __name__ == "__main__":
    main()
