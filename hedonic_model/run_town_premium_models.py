#!/usr/bin/env python3
"""Estimate clean good-school-count premium models separately by town."""

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


TOWN_FORMULA = """
log_resale_price ~ good_school_count_1km
+ floor_area_sqm + lease_age_years + remaining_lease_years + storey_mid
+ ln_nearest_mall_walking_distance_m + malls_within_10min_walk
+ ln_nearest_mrt_walking_distance_m + mrt_unique_lines_within_10min_walk
+ ln_nearest_bus_stop_walking_distance_m + bus_stops_within_5min_walk
+ ln_nearest_hawker_centre_walking_distance_m + hawker_centres_within_5min_walk
+ ln_nearest_supermarket_walking_distance_m + supermarkets_within_10min_walk
+ ln_nearest_park_walking_distance_m + parks_within_5min_walk
+ ln_nearest_pcn_walking_distance_m + pcns_within_5min_walk
+ C(flat_type) + C(flat_model) + C(month_period)
"""


def fit_town_model(town_df: pd.DataFrame, town: str) -> dict[str, float | int | str]:
    model = smf.ols(TOWN_FORMULA, data=town_df).fit()
    coef = float(model.params["good_school_count_1km"])
    std_err = float(model.bse["good_school_count_1km"])
    ci_low = coef - 1.96 * std_err
    ci_high = coef + 1.96 * std_err
    treated_share = float((town_df["good_school_count_1km"] > 0).mean())

    return {
        "town": town,
        "rows": int(model.nobs),
        "treated_share": treated_share,
        "coef_log_points": coef,
        "std_err": std_err,
        "p_value": float(model.pvalues["good_school_count_1km"]),
        "premium_pct_per_additional_good_school_1km": float(math.exp(coef) - 1),
        "ci_low_pct": float(math.exp(ci_low) - 1),
        "ci_high_pct": float(math.exp(ci_high) - 1),
        "r_squared": float(model.rsquared),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run town-specific premium models")
    parser.add_argument(
        "--input-csv",
        default="walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv",
        help="Input preprocessed feature CSV",
    )
    parser.add_argument(
        "--output-dir",
        default="hedonic_model/town_outputs",
        help="Directory for town-model outputs",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=1500,
        help="Minimum number of transaction rows required per town",
    )
    parser.add_argument(
        "--min-treated-share",
        type=float,
        default=0.05,
        help="Minimum treated share required per town",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(input_csv)
    model_df = engineer_features(raw_df)

    results: list[dict[str, float | int | str]] = []
    skipped: list[dict[str, float | int | str]] = []

    for town, town_df in model_df.groupby("town"):
        treated_share = float((town_df["good_school_count_1km"] > 0).mean())
        if len(town_df) < args.min_rows or treated_share < args.min_treated_share:
            skipped.append(
                {
                    "town": town,
                    "rows": int(len(town_df)),
                    "treated_share": treated_share,
                    "reason": "below_threshold",
                }
            )
            continue

        try:
            results.append(fit_town_model(town_df, town))
        except Exception as error:
            skipped.append(
                {
                    "town": town,
                    "rows": int(len(town_df)),
                    "treated_share": treated_share,
                    "reason": f"fit_failed: {type(error).__name__}",
                }
            )

    results_df = pd.DataFrame(results).sort_values(
        ["p_value", "premium_pct_per_additional_good_school_1km"],
        ascending=[True, False],
    )
    skipped_df = pd.DataFrame(skipped).sort_values(["rows"], ascending=False)

    results_df.to_csv(output_dir / "town_premium_results.csv", index=False)
    skipped_df.to_csv(output_dir / "town_premium_skipped.csv", index=False)
    (output_dir / "town_premium_results.json").write_text(results_df.to_json(orient="records", indent=2))

    print(results_df.to_string(index=False))
    print(f"\nSkipped towns: {len(skipped_df)}")
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
