#!/usr/bin/env python3
"""Trace how the good-school coefficient changes across nested specifications."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

try:
    from hedonic_model.train_hedonic_model import engineer_features
except ModuleNotFoundError:
    from train_hedonic_model import engineer_features  # type: ignore


SPECS = [
    {
        "name": "raw_only",
        "formula": "log_resale_price ~ good_school_within_1km",
    },
    {
        "name": "structural",
        "formula": (
            "log_resale_price ~ good_school_within_1km + floor_area_sqm + "
            "lease_age_years + remaining_lease_years + storey_mid + "
            "C(flat_type) + C(flat_model)"
        ),
    },
    {
        "name": "structural_plus_time",
        "formula": (
            "log_resale_price ~ good_school_within_1km + floor_area_sqm + "
            "lease_age_years + remaining_lease_years + storey_mid + "
            "C(flat_type) + C(flat_model) + C(month_period)"
        ),
    },
    {
        "name": "structural_plus_time_town",
        "formula": (
            "log_resale_price ~ good_school_within_1km + floor_area_sqm + "
            "lease_age_years + remaining_lease_years + storey_mid + "
            "C(flat_type) + C(flat_model) + C(month_period) + C(town)"
        ),
    },
    {
        "name": "add_access_amenities",
        "formula": (
            "log_resale_price ~ good_school_within_1km + floor_area_sqm + "
            "lease_age_years + remaining_lease_years + storey_mid + "
            "ln_nearest_mall_walking_distance_m + malls_within_10min_walk + "
            "ln_nearest_mrt_walking_distance_m + mrt_unique_lines_within_10min_walk + "
            "ln_nearest_bus_stop_walking_distance_m + bus_stops_within_5min_walk + "
            "ln_nearest_hawker_centre_walking_distance_m + hawker_centres_within_5min_walk + "
            "ln_nearest_supermarket_walking_distance_m + supermarkets_within_10min_walk + "
            "ln_nearest_park_walking_distance_m + parks_within_5min_walk + "
            "ln_nearest_pcn_walking_distance_m + pcns_within_5min_walk + "
            "C(flat_type) + C(flat_model) + C(month_period) + C(town)"
        ),
    },
    {
        "name": "add_school_counts",
        "formula": (
            "log_resale_price ~ good_school_within_1km + school_count_1km + "
            "good_school_count_1km + school_count_2km + good_school_count_2km + "
            "floor_area_sqm + lease_age_years + remaining_lease_years + storey_mid + "
            "ln_nearest_mall_walking_distance_m + malls_within_10min_walk + "
            "ln_nearest_mrt_walking_distance_m + mrt_unique_lines_within_10min_walk + "
            "ln_nearest_bus_stop_walking_distance_m + bus_stops_within_5min_walk + "
            "ln_nearest_hawker_centre_walking_distance_m + hawker_centres_within_5min_walk + "
            "ln_nearest_supermarket_walking_distance_m + supermarkets_within_10min_walk + "
            "ln_nearest_park_walking_distance_m + parks_within_5min_walk + "
            "ln_nearest_pcn_walking_distance_m + pcns_within_5min_walk + "
            "C(flat_type) + C(flat_model) + C(month_period) + C(town)"
        ),
    },
]


def fit_spec(data: pd.DataFrame, name: str, formula: str) -> dict[str, float | int | str]:
    model = smf.ols(formula, data=data).fit()
    coef = float(model.params["good_school_within_1km"])
    std_err = float(model.bse["good_school_within_1km"])
    ci_low = coef - 1.96 * std_err
    ci_high = coef + 1.96 * std_err
    return {
        "specification": name,
        "rows": int(model.nobs),
        "coef_log_points": coef,
        "std_err": std_err,
        "p_value": float(model.pvalues["good_school_within_1km"]),
        "premium_pct": float(math.exp(coef) - 1),
        "ci_low_pct": float(math.exp(ci_low) - 1),
        "ci_high_pct": float(math.exp(ci_high) - 1),
        "r_squared": float(model.rsquared),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace sign flips for the good-school indicator")
    parser.add_argument(
        "--input-csv",
        default="walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv",
        help="Input preprocessed feature CSV",
    )
    parser.add_argument(
        "--output-dir",
        default="hedonic_model/diagnostic_outputs",
        help="Directory for nested-spec diagnostics",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=100000,
        help="Sample size for fitting nested OLS specs",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducible sampling",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(input_csv)
    model_df = engineer_features(raw_df)
    if len(model_df) > args.sample_size:
        model_df = model_df.sample(n=args.sample_size, random_state=args.random_state).copy()

    results = [fit_spec(model_df, spec["name"], spec["formula"]) for spec in SPECS]
    results_df = pd.DataFrame(results)

    results_df.to_csv(output_dir / "good_school_sign_trace.csv", index=False)
    (output_dir / "good_school_sign_trace.json").write_text(results_df.to_json(orient="records", indent=2))

    print(results_df.to_string(index=False))
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
