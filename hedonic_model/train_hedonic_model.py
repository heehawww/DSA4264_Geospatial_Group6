#!/usr/bin/env python3
"""Train a baseline hedonic model for HDB resale prices."""

from __future__ import annotations

import argparse
import json
import joblib
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASELINE_NUMERIC_FEATURES = [
    "floor_area_sqm",
    "lease_age_years",
    "remaining_lease_years",
    "storey_mid",
    "sale_year",
    "sale_month",
    "months_since_start",
    "ln_nearest_mall_walking_distance_m",
    "malls_within_10min_walk",
    "ln_nearest_mrt_walking_distance_m",
    "mrt_unique_lines_within_10min_walk",
    "school_count_1km",
    "good_school_count_1km",
    "school_count_2km",
    "good_school_count_2km",
    "good_school_within_1km",
    "ln_nearest_bus_stop_walking_distance_m",
    "bus_stops_within_5min_walk",
    "ln_nearest_hawker_centre_walking_distance_m",
    "hawker_centres_within_5min_walk",
    "ln_nearest_supermarket_walking_distance_m",
    "supermarkets_within_10min_walk",
    "ln_nearest_park_walking_distance_m",
    "parks_within_5min_walk",
    "ln_nearest_pcn_walking_distance_m",
    "pcns_within_5min_walk",
]

REDUCED_NUMERIC_FEATURES = [
    "floor_area_sqm",
    "lease_age_years",
    "storey_mid",
    "months_since_start",
    "ln_nearest_mall_walking_distance_m",
    "malls_within_10min_walk",
    "ln_nearest_mrt_walking_distance_m",
    "mrt_unique_lines_within_10min_walk",
    "school_count_1km",
    "good_school_count_1km",
    "school_count_2km",
    "good_school_count_2km",
    "ln_nearest_bus_stop_walking_distance_m",
    "bus_stops_within_5min_walk",
    "ln_nearest_hawker_centre_walking_distance_m",
    "hawker_centres_within_5min_walk",
    "ln_nearest_supermarket_walking_distance_m",
    "supermarkets_within_10min_walk",
    "ln_nearest_park_walking_distance_m",
    "parks_within_5min_walk",
    "ln_nearest_pcn_walking_distance_m",
    "pcns_within_5min_walk",
]

FEATURE_SPECS = {
    "baseline": BASELINE_NUMERIC_FEATURES,
    "reduced": REDUCED_NUMERIC_FEATURES,
}

NUMERIC_FEATURES = BASELINE_NUMERIC_FEATURES
PREDICTIVE_CATEGORICAL_FEATURES = ["town", "flat_type", "flat_model"]

OLS_FORMULA = """
log_resale_price ~ floor_area_sqm + lease_age_years + remaining_lease_years + storey_mid
+ ln_nearest_mall_walking_distance_m + malls_within_10min_walk
+ ln_nearest_mrt_walking_distance_m + mrt_unique_lines_within_10min_walk
+ school_count_1km + good_school_count_1km + school_count_2km + good_school_count_2km
+ good_school_within_1km
+ ln_nearest_bus_stop_walking_distance_m + bus_stops_within_5min_walk
+ ln_nearest_hawker_centre_walking_distance_m + hawker_centres_within_5min_walk
+ ln_nearest_supermarket_walking_distance_m + supermarkets_within_10min_walk
+ ln_nearest_park_walking_distance_m + parks_within_5min_walk
+ ln_nearest_pcn_walking_distance_m + pcns_within_5min_walk
+ C(town) + C(flat_type) + C(flat_model) + C(month_period)
"""


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


def add_log_distance(df: pd.DataFrame, source: str) -> pd.Series:
    values = pd.to_numeric(df[source], errors="coerce").clip(lower=1)
    return np.log(values)


def engineer_features(df: pd.DataFrame, numeric_features: list[str] | None = None) -> pd.DataFrame:
    numeric_features = numeric_features or NUMERIC_FEATURES
    work = df.copy()
    work["month_dt"] = pd.to_datetime(work["month"], format="%Y-%m", errors="coerce")
    work["month_period"] = work["month_dt"].dt.to_period("M").astype(str)
    work["sale_year"] = work["month_dt"].dt.year
    work["sale_month"] = work["month_dt"].dt.month
    work["months_since_start"] = (
        (work["month_dt"].dt.year - work["month_dt"].dt.year.min()) * 12
        + (work["month_dt"].dt.month - work["month_dt"].dt.month.min())
    )
    work["remaining_lease_years"] = work["remaining_lease"].apply(parse_remaining_lease)
    work["storey_mid"] = work["storey_range"].apply(parse_storey_mid)
    work["lease_age_years"] = work["month_dt"].dt.year - pd.to_numeric(work["lease_commence_date"], errors="coerce")
    work["good_school_within_1km"] = (pd.to_numeric(work["good_school_count_1km"], errors="coerce") > 0).astype(int)
    work["log_resale_price"] = np.log(pd.to_numeric(work["resale_price"], errors="coerce"))

    for column in [
        "nearest_mall_walking_distance_m",
        "nearest_mrt_walking_distance_m",
        "nearest_bus_stop_walking_distance_m",
        "nearest_hawker_centre_walking_distance_m",
        "nearest_supermarket_walking_distance_m",
        "nearest_park_walking_distance_m",
        "nearest_pcn_walking_distance_m",
    ]:
        work[f"ln_{column}"] = add_log_distance(work, column)

    required_columns = ["log_resale_price", *BASELINE_NUMERIC_FEATURES, *PREDICTIVE_CATEGORICAL_FEATURES, "month_period"]
    work = work.dropna(subset=["log_resale_price", "month_dt", "floor_area_sqm", "resale_price"])

    for column in BASELINE_NUMERIC_FEATURES:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    return work[required_columns + ["resale_price", "month_dt"]].copy()


def time_split(df: pd.DataFrame, test_months: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_month = df["month_dt"].max()
    cutoff = (max_month.to_period("M") - test_months + 1).to_timestamp()
    train = df.loc[df["month_dt"] < cutoff].copy()
    test = df.loc[df["month_dt"] >= cutoff].copy()
    if train.empty or test.empty:
        raise ValueError("Time split produced an empty train or test set. Reduce --test-months.")
    return train, test


def fit_predictive_model(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric_features: list[str] | None = None,
    sample_weight: np.ndarray | None = None,
) -> tuple[Pipeline, dict[str, float], pd.DataFrame]:
    numeric_features = numeric_features or NUMERIC_FEATURES
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_features,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                PREDICTIVE_CATEGORICAL_FEATURES,
            ),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", Ridge(alpha=1.0)),
        ]
    )

    X_train = train[numeric_features + PREDICTIVE_CATEGORICAL_FEATURES]
    X_test = test[numeric_features + PREDICTIVE_CATEGORICAL_FEATURES]
    y_train = train["log_resale_price"]
    y_test = test["log_resale_price"]

    fit_kwargs = {}
    if sample_weight is not None:
        fit_kwargs["model__sample_weight"] = sample_weight

    pipeline.fit(X_train, y_train, **fit_kwargs)

    train_pred_log = pipeline.predict(X_train)
    test_pred_log = pipeline.predict(X_test)

    train_pred = np.exp(train_pred_log)
    test_pred = np.exp(test_pred_log)

    metrics = {
        "train_r2_log": float(r2_score(y_train, train_pred_log)),
        "test_r2_log": float(r2_score(y_test, test_pred_log)),
        "train_rmse_sgd": float(math.sqrt(mean_squared_error(train["resale_price"], train_pred))),
        "test_rmse_sgd": float(math.sqrt(mean_squared_error(test["resale_price"], test_pred))),
        "train_mae_sgd": float(mean_absolute_error(train["resale_price"], train_pred)),
        "test_mae_sgd": float(mean_absolute_error(test["resale_price"], test_pred)),
    }

    feature_names = pipeline.named_steps["preprocessor"].get_feature_names_out()
    coefficients = pipeline.named_steps["model"].coef_
    feature_importance = (
        pd.DataFrame({"feature": feature_names, "coefficient": coefficients})
        .assign(abs_coefficient=lambda frame: frame["coefficient"].abs())
        .sort_values("abs_coefficient", ascending=False)
    )

    return pipeline, metrics, feature_importance


def rebalance_by_floor_area(
    train_df: pd.DataFrame,
    bins: int,
    target_fraction: float,
    random_state: int,
) -> pd.DataFrame:
    """Upsample underrepresented floor-area bins for regression training."""
    work = train_df.copy()
    work["floor_area_bin"] = pd.qcut(work["floor_area_sqm"], q=bins, duplicates="drop")
    bin_counts = work["floor_area_bin"].value_counts()
    target_size = int(bin_counts.quantile(target_fraction))

    sampled_frames = []
    rng = np.random.default_rng(random_state)
    for _, group in work.groupby("floor_area_bin", observed=False):
        replace = len(group) < target_size
        sample_n = max(len(group), target_size)
        indices = rng.choice(group.index.to_numpy(), size=sample_n, replace=replace)
        sampled_frames.append(group.loc[indices])

    return pd.concat(sampled_frames, ignore_index=True).drop(columns=["floor_area_bin"])


def build_floor_area_sample_weights(
    train_df: pd.DataFrame,
    bins: int,
    target_fraction: float,
) -> np.ndarray:
    """Upweight underrepresented floor-area bins without duplicating rows."""
    work = train_df[["floor_area_sqm"]].copy()
    work["floor_area_bin"] = pd.qcut(work["floor_area_sqm"], q=bins, duplicates="drop")
    bin_counts = work["floor_area_bin"].value_counts()
    target_size = float(bin_counts.quantile(target_fraction))

    bin_weights = {
        bin_value: max(1.0, target_size / float(count))
        for bin_value, count in bin_counts.items()
    }
    weights = work["floor_area_bin"].map(bin_weights).astype(float).to_numpy()
    return weights


def fit_ols_model(train: pd.DataFrame, max_rows: int, random_state: int) -> tuple[pd.DataFrame, object, float, int]:
    ols_train = train.sample(n=max_rows, random_state=random_state) if len(train) > max_rows else train
    ols_model = smf.ols(OLS_FORMULA, data=ols_train).fit()
    coefficients = (
        ols_model.summary2().tables[1]
        .reset_index()
        .rename(columns={"index": "term"})
    )

    if "good_school_within_1km" in coefficients["term"].values:
        beta = coefficients.loc[coefficients["term"] == "good_school_within_1km", "Coef."].iloc[0]
        premium_pct = math.exp(beta) - 1
    else:
        premium_pct = float("nan")

    return coefficients, ols_model, premium_pct, len(ols_train)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a baseline HDB hedonic model")
    parser.add_argument(
        "--input-csv",
        default="data/feature_engineering/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv",
        help="Input preprocessed feature CSV",
    )
    parser.add_argument(
        "--output-dir",
        default="hedonic_model/outputs",
        help="Directory for model artifacts",
    )
    parser.add_argument(
        "--test-months",
        type=int,
        default=12,
        help="Number of most recent months held out for testing",
    )
    parser.add_argument(
        "--ols-max-rows",
        type=int,
        default=100000,
        help="Maximum number of training rows used for OLS coefficient estimation",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducible OLS sampling",
    )
    parser.add_argument(
        "--feature-spec",
        choices=sorted(FEATURE_SPECS.keys()),
        default="reduced",
        help="Predictive feature specification to use",
    )
    parser.add_argument(
        "--rebalance-floor-area",
        action="store_true",
        help="Upsample underrepresented floor-area bins before fitting the predictive Ridge model",
    )
    parser.add_argument(
        "--weight-floor-area",
        action="store_true",
        help="Upweight underrepresented floor-area bins when fitting the predictive Ridge model",
    )
    parser.add_argument(
        "--rebalance-bins",
        type=int,
        default=8,
        help="Number of quantile bins used for floor-area rebalancing",
    )
    parser.add_argument(
        "--rebalance-target-fraction",
        type=float,
        default=0.75,
        help="Target quantile of bin size to rebalance toward",
    )
    args = parser.parse_args()

    if args.rebalance_floor_area and args.weight_floor_area:
        raise ValueError("Choose only one of --rebalance-floor-area or --weight-floor-area")

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    numeric_features = FEATURE_SPECS[args.feature_spec]
    print(f"Loading {input_csv} ...")
    raw = pd.read_csv(input_csv)
    model_df = engineer_features(raw, numeric_features=numeric_features)
    train_df, test_df = time_split(model_df, args.test_months)
    predictive_train_df = train_df
    predictive_sample_weight = None
    if args.rebalance_floor_area:
        predictive_train_df = rebalance_by_floor_area(
            train_df,
            bins=args.rebalance_bins,
            target_fraction=args.rebalance_target_fraction,
            random_state=args.random_state,
        )
    elif args.weight_floor_area:
        predictive_sample_weight = build_floor_area_sample_weights(
            train_df,
            bins=args.rebalance_bins,
            target_fraction=args.rebalance_target_fraction,
        )

    print(f"Training rows: {len(train_df):,}")
    print(f"Testing rows: {len(test_df):,}")
    if args.rebalance_floor_area:
        print(f"Rebalanced training rows: {len(predictive_train_df):,}")
    if args.weight_floor_area and predictive_sample_weight is not None:
        print(
            "Floor-area sample weights:"
            f" min={predictive_sample_weight.min():.3f},"
            f" max={predictive_sample_weight.max():.3f},"
            f" mean={predictive_sample_weight.mean():.3f}"
        )

    ridge_pipeline, metrics, feature_importance = fit_predictive_model(
        predictive_train_df,
        test_df,
        numeric_features=numeric_features,
        sample_weight=predictive_sample_weight,
    )
    joblib.dump(ridge_pipeline, output_dir / "ridge_pipeline.pkl")
    print(f"Saved Ridge pipeline to {output_dir / 'ridge_pipeline.pkl'}")
    coefficients, ols_model, premium_pct, ols_rows = fit_ols_model(
        train_df,
        max_rows=args.ols_max_rows,
        random_state=args.random_state,
    )

    metrics["rows_total"] = int(len(model_df))
    metrics["rows_train"] = int(len(train_df))
    metrics["rows_train_predictive"] = int(len(predictive_train_df))
    metrics["rows_test"] = int(len(test_df))
    metrics["rows_ols"] = int(ols_rows)
    metrics["feature_spec"] = args.feature_spec
    metrics["rebalance_floor_area"] = bool(args.rebalance_floor_area)
    metrics["weight_floor_area"] = bool(args.weight_floor_area)
    metrics["rebalance_bins"] = int(args.rebalance_bins)
    metrics["rebalance_target_fraction"] = float(args.rebalance_target_fraction)
    if predictive_sample_weight is not None:
        metrics["floor_area_weight_min"] = float(predictive_sample_weight.min())
        metrics["floor_area_weight_max"] = float(predictive_sample_weight.max())
        metrics["floor_area_weight_mean"] = float(predictive_sample_weight.mean())
    metrics["good_school_within_1km_premium_pct_from_ols"] = float(premium_pct)

    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    feature_importance.head(100).to_csv(output_dir / "feature_importance_top.csv", index=False)
    coefficients.to_csv(output_dir / "ols_coefficients.csv", index=False)
    (output_dir / "model_summary.txt").write_text(ols_model.summary().as_text())

    print(json.dumps(metrics, indent=2))
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
