#!/usr/bin/env python3
"""Run a boundary-based RDD around the 1km good-school cutoff."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from shapely.strtree import STRtree

SVY21_EPSG = 3414

BASE_CONTROLS = [
    "floor_area_sqm",
    "lease_age_years",
    "remaining_lease_years",
    "storey_mid",
]


def parse_remaining_lease(value: object) -> float:
    if pd.isna(value):
        return np.nan

    text = str(value).strip().lower()
    year_match = re.search(r"(\d+)\s+year", text)
    month_match = re.search(r"(\d+)\s+month", text)
    years = int(year_match.group(1)) if year_match else 0
    months = int(month_match.group(1)) if month_match else 0
    return years + months / 12


def parse_storey_mid(value: object) -> float:
    if pd.isna(value):
        return np.nan

    numbers = [int(number) for number in re.findall(r"\d+", str(value))]
    if not numbers:
        return np.nan
    if len(numbers) == 1:
        return float(numbers[0])
    return float(sum(numbers[:2]) / 2)


def normalise_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def engineer_transaction_features(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["month_dt"] = pd.to_datetime(work["month"], format="%Y-%m", errors="coerce")
    work["month_period"] = work["month_dt"].dt.to_period("M").astype(str)
    work["remaining_lease_years"] = work["remaining_lease"].apply(parse_remaining_lease)
    work["storey_mid"] = work["storey_range"].apply(parse_storey_mid)
    work["lease_age_years"] = work["month_dt"].dt.year - pd.to_numeric(work["lease_commence_date"], errors="coerce")
    work["log_resale_price"] = np.log(pd.to_numeric(work["resale_price"], errors="coerce"))

    keep = [
        "address_key",
        "month",
        "month_dt",
        "month_period",
        "town",
        "flat_type",
        "flat_model",
        "resale_price",
        "log_resale_price",
        *BASE_CONTROLS,
    ]

    work = work.dropna(subset=["address_key", "month_dt", "resale_price", "log_resale_price"])
    for column in BASE_CONTROLS:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work[keep].copy()


def load_points(points_path: Path) -> gpd.GeoDataFrame:
    points = gpd.read_file(points_path)
    if points.crs is None:
        points = points.set_crs(4326)
    return points.to_crs(SVY21_EPSG)


def load_good_school_buffers(buffers_path: Path) -> gpd.GeoDataFrame:
    buffers = gpd.read_file(buffers_path)
    if buffers.crs is None:
        buffers = buffers.set_crs(4326)
    buffers = buffers.to_crs(SVY21_EPSG)
    buffers["is_good_school"] = normalise_bool(buffers["is_good_school"])
    buffers = buffers.loc[buffers["is_good_school"]].copy()
    if buffers.empty:
        raise ValueError("No good-school polygons found in buffer layer.")
    return buffers


def compute_signed_distances(points: gpd.GeoDataFrame, buffers: gpd.GeoDataFrame) -> pd.DataFrame:
    boundaries = list(buffers.geometry.boundary)
    tree = STRtree(boundaries)
    index_lookup = {geometry.wkb: idx for idx, geometry in enumerate(boundaries)}

    rows: list[dict[str, object]] = []
    for point_row in points.itertuples(index=False):
        nearest_boundary = tree.nearest(point_row.geometry)
        if isinstance(nearest_boundary, (int, np.integer)):
            boundary_idx = int(nearest_boundary)
            boundary_geom = boundaries[boundary_idx]
        else:
            boundary_idx = index_lookup[nearest_boundary.wkb]
            boundary_geom = nearest_boundary
        school_row = buffers.iloc[boundary_idx]
        distance_m = float(point_row.geometry.distance(boundary_geom))
        inside = bool(school_row.geometry.covers(point_row.geometry))
        rows.append(
            {
                "address_key": point_row.address_key,
                "boundary_school_name": school_row.school_name,
                "boundary_school_join_key": school_row.join_key,
                "overall_subscription_rates": school_row.get("overall_subscription_rates", np.nan),
                "signed_distance_m": -distance_m if inside else distance_m,
                "inside_good_school_1km": int(inside),
            }
        )

    return pd.DataFrame(rows)


def triangular_weights(distance_abs_m: pd.Series, bandwidth_m: int) -> pd.Series:
    weights = 1 - distance_abs_m / bandwidth_m
    return weights.clip(lower=0)


def run_local_linear_rdd(df: pd.DataFrame, bandwidth_m: int, specification: str) -> tuple[object, pd.DataFrame]:
    local = df.loc[df["distance_abs_m"] <= bandwidth_m].copy()
    if local.empty:
        raise ValueError(f"No observations within {bandwidth_m}m bandwidth.")

    local["running_km"] = local["signed_distance_m"] / 1000
    local["treat"] = (local["signed_distance_m"] <= 0).astype(int)
    local["kernel_weight"] = triangular_weights(local["distance_abs_m"], bandwidth_m)

    formula = "log_resale_price ~ treat + running_km + treat:running_km"
    if specification in {"controlled", "school_fe"}:
        formula += " + floor_area_sqm + lease_age_years + remaining_lease_years + storey_mid"
        formula += " + C(town) + C(flat_type) + C(flat_model) + C(month_period)"
    if specification == "school_fe":
        formula += " + C(boundary_school_name)"

    model = smf.wls(formula, data=local, weights=local["kernel_weight"]).fit(cov_type="HC1")
    table = (
        model.summary2().tables[1]
        .reset_index()
        .rename(columns={"index": "term"})
    )
    return model, table


def extract_rdd_metrics(model: object, bandwidth_m: int, sample_size: int, spec_name: str) -> dict[str, float | int | str]:
    if "treat" not in model.params.index:
        raise ValueError("RDD model did not estimate a treatment jump.")

    coef = float(model.params["treat"])
    std_err = float(model.bse["treat"])
    ci_low = coef - 1.96 * std_err
    ci_high = coef + 1.96 * std_err
    return {
        "specification": spec_name,
        "bandwidth_m": int(bandwidth_m),
        "sample_size": int(sample_size),
        "cutoff_coef_log_points": coef,
        "cutoff_std_err": std_err,
        "cutoff_p_value": float(model.pvalues["treat"]),
        "cutoff_premium_pct": float(math.exp(coef) - 1),
        "cutoff_ci_low_pct": float(math.exp(ci_low) - 1),
        "cutoff_ci_high_pct": float(math.exp(ci_high) - 1),
        "r_squared": float(model.rsquared),
    }


def run_balance_check(df: pd.DataFrame, bandwidth_m: int, outcome: str) -> dict[str, float | int | str]:
    local = df.loc[df["distance_abs_m"] <= bandwidth_m].copy()
    local["running_km"] = local["signed_distance_m"] / 1000
    local["treat"] = (local["signed_distance_m"] <= 0).astype(int)
    local["kernel_weight"] = triangular_weights(local["distance_abs_m"], bandwidth_m)

    model = smf.wls(
        f"{outcome} ~ treat + running_km + treat:running_km",
        data=local,
        weights=local["kernel_weight"],
    ).fit(cov_type="HC1")

    return {
        "outcome": outcome,
        "bandwidth_m": int(bandwidth_m),
        "sample_size": int(len(local)),
        "cutoff_coef": float(model.params["treat"]),
        "cutoff_std_err": float(model.bse["treat"]),
        "cutoff_p_value": float(model.pvalues["treat"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Boundary RDD around the 1km good-school cutoff")
    parser.add_argument(
        "--transactions-csv",
        default="walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv",
        help="Transaction-level feature CSV",
    )
    parser.add_argument(
        "--points-geojson",
        default="primary_boundaries/outputs/resale_address_points_matched_with_school_counts.geojson",
        help="GeoJSON of matched HDB address points",
    )
    parser.add_argument(
        "--buffers-geojson",
        default="primary_boundaries/outputs/primary_school_boundaries_buffer_1km.geojson",
        help="GeoJSON of 1km school buffers",
    )
    parser.add_argument(
        "--output-dir",
        default="hedonic_model/rdd_outputs",
        help="Directory for RDD outputs",
    )
    parser.add_argument(
        "--bandwidths",
        nargs="+",
        type=int,
        default=[100, 200, 300, 500],
        help="Bandwidths in meters for local linear RDD",
    )
    args = parser.parse_args()

    transactions_path = Path(args.transactions_csv)
    points_path = Path(args.points_geojson)
    buffers_path = Path(args.buffers_geojson)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not transactions_path.exists():
        raise FileNotFoundError(f"Missing transactions CSV: {transactions_path}")
    if not points_path.exists():
        raise FileNotFoundError(f"Missing points GeoJSON: {points_path}")
    if not buffers_path.exists():
        raise FileNotFoundError(f"Missing school buffer GeoJSON: {buffers_path}")

    print("Loading transactions...")
    transactions = engineer_transaction_features(pd.read_csv(transactions_path))

    print("Loading geocoded HDB address points...")
    points = load_points(points_path)[["address_key", "geometry"]].copy()

    print("Loading good-school 1km buffers...")
    buffers = load_good_school_buffers(buffers_path)

    print("Computing signed distances to nearest good-school buffer boundary...")
    signed_distances = compute_signed_distances(points, buffers)
    signed_distances = (
        signed_distances.sort_values("signed_distance_m", key=lambda series: series.abs())
        .drop_duplicates(subset=["address_key"], keep="first")
        .copy()
    )

    model_df = transactions.merge(signed_distances, on="address_key", how="inner", validate="m:1")
    model_df["distance_abs_m"] = model_df["signed_distance_m"].abs()
    model_df = model_df.dropna(
        subset=[
            "log_resale_price",
            "floor_area_sqm",
            "lease_age_years",
            "remaining_lease_years",
            "storey_mid",
            "signed_distance_m",
        ]
    )

    signed_distances.to_csv(output_dir / "address_signed_distances.csv", index=False)
    model_df.head(2000).to_csv(output_dir / "rdd_sample_preview.csv", index=False)

    results: list[dict[str, float | int | str]] = []
    coefficient_tables: list[pd.DataFrame] = []
    balance_rows: list[dict[str, float | int | str]] = []

    for bandwidth_m in args.bandwidths:
        for spec_name in ("uncontrolled", "controlled", "school_fe"):
            print(f"Estimating {spec_name} RDD at {bandwidth_m}m bandwidth...")
            model, coef_table = run_local_linear_rdd(model_df, bandwidth_m=bandwidth_m, specification=spec_name)
            local_n = int((model_df["distance_abs_m"] <= bandwidth_m).sum())
            results.append(extract_rdd_metrics(model, bandwidth_m, local_n, spec_name))
            coefficient_tables.append(coef_table.assign(specification=spec_name, bandwidth_m=bandwidth_m))

        for outcome in BASE_CONTROLS:
            balance_rows.append(run_balance_check(model_df, bandwidth_m=bandwidth_m, outcome=outcome))

    results_df = pd.DataFrame(results).sort_values(["bandwidth_m", "specification"])
    coef_df = pd.concat(coefficient_tables, ignore_index=True)
    balance_df = pd.DataFrame(balance_rows).sort_values(["bandwidth_m", "outcome"])

    results_df.to_csv(output_dir / "rdd_results.csv", index=False)
    coef_df.to_csv(output_dir / "rdd_coefficients.csv", index=False)
    balance_df.to_csv(output_dir / "rdd_covariate_balance.csv", index=False)
    (output_dir / "rdd_results.json").write_text(results_df.to_json(orient="records", indent=2))

    summary = {
        "transactions_with_geocoded_addresses": int(model_df["address_key"].nunique()),
        "transaction_rows_used": int(len(model_df)),
        "good_school_buffers": int(len(buffers)),
        "bandwidths_m": args.bandwidths,
    }
    (output_dir / "rdd_summary.json").write_text(json.dumps(summary, indent=2))

    print(results_df.to_string(index=False))
    print(f"Wrote RDD outputs to {output_dir}")


if __name__ == "__main__":
    main()
