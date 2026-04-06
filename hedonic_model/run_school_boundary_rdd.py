#!/usr/bin/env python3
"""Run school-specific boundary RDDs around 1km school cutoffs."""

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


def load_school_buffers(buffers_path: Path) -> gpd.GeoDataFrame:
    buffers = gpd.read_file(buffers_path)
    if buffers.crs is None:
        buffers = buffers.set_crs(4326)
    buffers = buffers.to_crs(SVY21_EPSG)
    buffers["is_good_school"] = normalise_bool(buffers["is_good_school"])
    if buffers.empty:
        raise ValueError("No school polygons found in buffer layer.")
    return buffers


def compute_school_specific_distances(
    points: gpd.GeoDataFrame,
    buffers: gpd.GeoDataFrame,
    max_bandwidth_m: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for school_row in buffers.itertuples(index=False):
        boundary = school_row.geometry.boundary
        for point_row in points.itertuples(index=False):
            distance_m = float(point_row.geometry.distance(boundary))
            if distance_m > max_bandwidth_m:
                continue
            inside = bool(school_row.geometry.covers(point_row.geometry))
            rows.append(
                {
                    "address_key": point_row.address_key,
                    "boundary_school_name": school_row.school_name,
                    "boundary_school_join_key": school_row.join_key,
                    "is_good_school": bool(school_row.is_good_school),
                    "overall_subscription_rates": getattr(school_row, "overall_subscription_rates", np.nan),
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


def extract_rdd_metrics(
    model: object,
    local_df: pd.DataFrame,
    bandwidth_m: int,
    sample_size: int,
    spec_name: str,
) -> dict[str, float | int | str]:
    if "treat" not in model.params.index:
        raise ValueError("RDD model did not estimate a treatment jump.")

    coef = float(model.params["treat"])
    std_err = float(model.bse["treat"])
    ci_low = coef - 1.96 * std_err
    ci_high = coef + 1.96 * std_err
    premium_pct = float(math.exp(coef) - 1)
    mean_price = float(local_df["resale_price"].mean())
    median_price = float(local_df["resale_price"].median())
    return {
        "specification": spec_name,
        "bandwidth_m": int(bandwidth_m),
        "sample_size": int(sample_size),
        "cutoff_coef_log_points": coef,
        "cutoff_std_err": std_err,
        "cutoff_p_value": float(model.pvalues["treat"]),
        "cutoff_premium_pct": premium_pct,
        "cutoff_price_jump_sgd_at_local_mean_price": premium_pct * mean_price,
        "cutoff_price_jump_sgd_at_local_median_price": premium_pct * median_price,
        "local_mean_resale_price": mean_price,
        "local_median_resale_price": median_price,
        "cutoff_ci_low_pct": float(math.exp(ci_low) - 1),
        "cutoff_ci_high_pct": float(math.exp(ci_high) - 1),
        "r_squared": float(model.rsquared),
    }


def run_school_specific_rdd(
    model_df: pd.DataFrame,
    bandwidths: list[int],
    min_total: int,
    min_each_side: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    results: list[dict[str, float | int | str]] = []
    coefficient_tables: list[pd.DataFrame] = []
    skipped: list[dict[str, float | int | str]] = []

    for (school_name, is_good_school), school_df in model_df.groupby(["boundary_school_name", "is_good_school"]):
        for bandwidth_m in bandwidths:
            local_df = school_df.loc[school_df["distance_abs_m"] <= bandwidth_m].copy()
            inside_n = int((local_df["signed_distance_m"] <= 0).sum())
            outside_n = int((local_df["signed_distance_m"] > 0).sum())
            total_n = int(len(local_df))

            if total_n < min_total or inside_n < min_each_side or outside_n < min_each_side:
                skipped.append(
                    {
                        "boundary_school_name": school_name,
                        "school_group": "good" if bool(is_good_school) else "non_good",
                        "bandwidth_m": int(bandwidth_m),
                        "sample_size": total_n,
                        "inside_n": inside_n,
                        "outside_n": outside_n,
                        "reason": "insufficient_boundary_sample",
                    }
                )
                continue

            for spec_name in ("uncontrolled", "controlled"):
                model, coef_table = run_local_linear_rdd(
                    school_df,
                    bandwidth_m=bandwidth_m,
                    specification=spec_name,
                )
                result = extract_rdd_metrics(model, local_df, bandwidth_m, total_n, spec_name)
                result["boundary_school_name"] = school_name
                result["school_group"] = "good" if bool(is_good_school) else "non_good"
                result["inside_n"] = inside_n
                result["outside_n"] = outside_n
                results.append(result)
                coefficient_tables.append(
                    coef_table.assign(
                        boundary_school_name=school_name,
                        school_group="good" if bool(is_good_school) else "non_good",
                        specification=spec_name,
                        bandwidth_m=bandwidth_m,
                    )
                )

    if results:
        results_df = pd.DataFrame(results).sort_values(["boundary_school_name", "bandwidth_m", "specification"])
    else:
        results_df = pd.DataFrame(
            columns=[
                "boundary_school_name",
                "specification",
                "bandwidth_m",
                "sample_size",
                "inside_n",
                "outside_n",
            ]
        )
    coef_df = pd.concat(coefficient_tables, ignore_index=True) if coefficient_tables else pd.DataFrame()
    skipped_df = (
        pd.DataFrame(skipped).sort_values(["boundary_school_name", "bandwidth_m"])
        if skipped
        else pd.DataFrame(columns=["boundary_school_name", "bandwidth_m", "sample_size", "inside_n", "outside_n", "reason"])
    )
    return results_df, coef_df, skipped_df


def main() -> None:
    parser = argparse.ArgumentParser(description="School-specific boundary RDD around 1km school cutoffs")
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
    parser.add_argument(
        "--school-min-total",
        type=int,
        default=150,
        help="Minimum total local observations required for school-specific RDD",
    )
    parser.add_argument(
        "--school-min-each-side",
        type=int,
        default=40,
        help="Minimum observations required on each side of the cutoff for school-specific RDD",
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

    print("Loading 1km school buffers...")
    buffers = load_school_buffers(buffers_path)
    max_bandwidth_m = max(args.bandwidths)
    print("Computing school-specific signed distances near each school boundary...")
    school_specific_distances = compute_school_specific_distances(points, buffers, max_bandwidth_m=max_bandwidth_m)
    school_specific_model_df = transactions.merge(
        school_specific_distances,
        on="address_key",
        how="inner",
        validate="m:m",
    )
    school_specific_model_df["distance_abs_m"] = school_specific_model_df["signed_distance_m"].abs()
    school_specific_model_df = school_specific_model_df.dropna(
        subset=[
            "log_resale_price",
            "floor_area_sqm",
            "lease_age_years",
            "remaining_lease_years",
            "storey_mid",
            "signed_distance_m",
        ]
    )

    school_results_df, school_coef_df, school_skipped_df = run_school_specific_rdd(
        school_specific_model_df,
        bandwidths=args.bandwidths,
        min_total=args.school_min_total,
        min_each_side=args.school_min_each_side,
    )

    school_specific_distances.to_csv(output_dir / "school_specific_address_signed_distances.csv", index=False)
    school_results_df.to_csv(output_dir / "school_specific_rdd_results.csv", index=False)
    school_coef_df.to_csv(output_dir / "school_specific_rdd_coefficients.csv", index=False)
    school_skipped_df.to_csv(output_dir / "school_specific_rdd_skipped.csv", index=False)
    (output_dir / "school_specific_rdd_results.json").write_text(
        school_results_df.to_json(orient="records", indent=2)
    )

    summary = {
        "transactions_with_geocoded_addresses": int(transactions["address_key"].nunique()),
        "transaction_rows_used": int(len(transactions)),
        "school_buffers_total": int(len(buffers)),
        "school_buffers_good": int(buffers["is_good_school"].sum()),
        "school_buffers_non_good": int((~buffers["is_good_school"]).sum()),
        "bandwidths_m": args.bandwidths,
        "school_specific_rows_used": int(len(school_specific_model_df)),
        "school_specific_schools_with_results": int(school_results_df["boundary_school_name"].nunique()) if not school_results_df.empty else 0,
    }
    (output_dir / "rdd_summary.json").write_text(json.dumps(summary, indent=2))

    if not school_results_df.empty:
        print("\nSchool-specific RDD results:")
        print(school_results_df.to_string(index=False))
    print(f"Wrote RDD outputs to {output_dir}")


if __name__ == "__main__":
    main()
