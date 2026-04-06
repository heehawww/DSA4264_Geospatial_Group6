#!/usr/bin/env python3
"""Benchmark feature-reduction and regression variants for the hedonic model."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNetCV, LassoCV, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor

try:
    from hedonic_model.train_hedonic_model import (
        BASELINE_NUMERIC_FEATURES,
        PREDICTIVE_CATEGORICAL_FEATURES,
        REDUCED_NUMERIC_FEATURES,
        engineer_features,
        time_split,
    )
except ModuleNotFoundError:
    from train_hedonic_model import (  # type: ignore
        BASELINE_NUMERIC_FEATURES,
        PREDICTIVE_CATEGORICAL_FEATURES,
        REDUCED_NUMERIC_FEATURES,
        engineer_features,
        time_split,
    )


def compute_metrics(y_true_log: pd.Series, y_pred_log: np.ndarray, y_true_price: pd.Series) -> dict[str, float]:
    y_pred_price = np.exp(y_pred_log)
    return {
        "r2_log": float(r2_score(y_true_log, y_pred_log)),
        "rmse_sgd": float(math.sqrt(mean_squared_error(y_true_price, y_pred_price))),
        "mae_sgd": float(mean_absolute_error(y_true_price, y_pred_price)),
    }


def build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
    selector: SelectKBest | None = None,
) -> ColumnTransformer:
    numeric_steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]
    if selector is not None:
        numeric_steps.append(("selector", selector))

    return ColumnTransformer(
        transformers=[
            ("num", Pipeline(steps=numeric_steps), numeric_features),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
        ]
    )


def fit_and_score(
    name: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    numeric_features: list[str],
    regressor,
    selector: SelectKBest | None = None,
    sample_weight: np.ndarray | None = None,
) -> dict[str, float | str | int]:
    categorical_features = PREDICTIVE_CATEGORICAL_FEATURES
    preprocessor = build_preprocessor(numeric_features, categorical_features, selector=selector)
    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", regressor),
        ]
    )

    X_train = train_df[numeric_features + categorical_features]
    X_test = test_df[numeric_features + categorical_features]
    y_train = train_df["log_resale_price"]
    y_test = test_df["log_resale_price"]

    fit_kwargs = {}
    if sample_weight is not None:
        fit_kwargs["model__sample_weight"] = sample_weight

    pipeline.fit(X_train, y_train, **fit_kwargs)
    test_pred_log = pipeline.predict(X_test)
    train_pred_log = pipeline.predict(X_train)

    train_metrics = compute_metrics(y_train, train_pred_log, train_df["resale_price"])
    test_metrics = compute_metrics(y_test, test_pred_log, test_df["resale_price"])

    result = {
        "variant": name,
        "numeric_feature_count": int(len(numeric_features)),
        "train_r2_log": train_metrics["r2_log"],
        "test_r2_log": test_metrics["r2_log"],
        "train_rmse_sgd": train_metrics["rmse_sgd"],
        "test_rmse_sgd": test_metrics["rmse_sgd"],
        "train_mae_sgd": train_metrics["mae_sgd"],
        "test_mae_sgd": test_metrics["mae_sgd"],
    }

    model = pipeline.named_steps["model"]
    if hasattr(model, "alpha_"):
        result["alpha"] = float(model.alpha_)
    if hasattr(model, "l1_ratio_"):
        result["l1_ratio"] = float(model.l1_ratio_)
    if selector is not None:
        support = pipeline.named_steps["preprocessor"].named_transformers_["num"].named_steps["selector"].get_support()
        selected_numeric = [feature for feature, keep in zip(numeric_features, support) if keep]
        result["selected_numeric_features"] = ", ".join(selected_numeric)

    return result


def iterative_vif_prune(
    train_df: pd.DataFrame,
    numeric_features: list[str],
    threshold: float,
) -> list[str]:
    features = numeric_features.copy()

    while len(features) > 2:
        X = train_df[features].fillna(train_df[features].median())
        vif_scores = []
        for index, feature in enumerate(features):
            vif = variance_inflation_factor(X.values, index)
            vif_scores.append((feature, vif))
        worst_feature, worst_vif = max(vif_scores, key=lambda item: item[1])
        if worst_vif <= threshold:
            break
        features.remove(worst_feature)

    return features


def rebalance_by_floor_area(
    train_df: pd.DataFrame,
    bins: int,
    target_fraction: float,
    random_state: int,
) -> pd.DataFrame:
    work = train_df.copy()
    work["floor_area_bin"] = pd.qcut(work["floor_area_sqm"], q=bins, duplicates="drop")
    bin_counts = work["floor_area_bin"].value_counts()
    target_size = int(bin_counts.quantile(target_fraction))

    sampled_frames = []
    rng = np.random.default_rng(random_state)
    for bin_value, group in work.groupby("floor_area_bin", observed=False):
        replace = len(group) < target_size
        sample_n = max(len(group), target_size)
        indices = rng.choice(group.index.to_numpy(), size=sample_n, replace=replace)
        sampled_frames.append(group.loc[indices])

    balanced = pd.concat(sampled_frames, ignore_index=True).drop(columns=["floor_area_bin"])
    return balanced


def build_floor_area_sample_weights(
    train_df: pd.DataFrame,
    bins: int,
    target_fraction: float,
) -> np.ndarray:
    work = train_df[["floor_area_sqm"]].copy()
    work["floor_area_bin"] = pd.qcut(work["floor_area_sqm"], q=bins, duplicates="drop")
    bin_counts = work["floor_area_bin"].value_counts()
    target_size = float(bin_counts.quantile(target_fraction))
    bin_weights = {
        bin_value: max(1.0, target_size / float(count))
        for bin_value, count in bin_counts.items()
    }
    return work["floor_area_bin"].map(bin_weights).astype(float).to_numpy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark alternative hedonic-model variants")
    parser.add_argument(
        "--input-csv",
        default="walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv",
        help="Input preprocessed feature CSV",
    )
    parser.add_argument(
        "--output-dir",
        default="hedonic_model/benchmark_outputs",
        help="Directory for benchmark outputs",
    )
    parser.add_argument(
        "--test-months",
        type=int,
        default=12,
        help="Number of most recent months held out for testing",
    )
    parser.add_argument(
        "--vif-threshold",
        type=float,
        default=10.0,
        help="VIF threshold for iterative numeric feature pruning",
    )
    parser.add_argument(
        "--anova-k",
        type=int,
        default=12,
        help="Number of numeric features to keep for f_regression selection",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(input_csv)
    model_df = engineer_features(raw_df)
    train_df, test_df = time_split(model_df, args.test_months)

    vif_pruned_features = iterative_vif_prune(train_df, BASELINE_NUMERIC_FEATURES, threshold=args.vif_threshold)
    selector_k = min(args.anova_k, len(REDUCED_NUMERIC_FEATURES))

    benchmark_rows: list[dict[str, float | str | int]] = []

    benchmark_rows.append(
        fit_and_score(
            "ridge_baseline",
            train_df,
            test_df,
            BASELINE_NUMERIC_FEATURES,
            Ridge(alpha=1.0),
        )
    )
    benchmark_rows.append(
        fit_and_score(
            "ridge_reduced",
            train_df,
            test_df,
            REDUCED_NUMERIC_FEATURES,
            Ridge(alpha=1.0),
        )
    )
    benchmark_rows.append(
        fit_and_score(
            "ridge_vif_pruned",
            train_df,
            test_df,
            vif_pruned_features,
            Ridge(alpha=1.0),
        )
    )
    benchmark_rows.append(
        fit_and_score(
            "ridge_f_regression",
            train_df,
            test_df,
            REDUCED_NUMERIC_FEATURES,
            Ridge(alpha=1.0),
            selector=SelectKBest(score_func=f_regression, k=selector_k),
        )
    )
    benchmark_rows.append(
        fit_and_score(
            "lasso_reduced",
            train_df,
            test_df,
            REDUCED_NUMERIC_FEATURES,
            LassoCV(
                alphas=np.logspace(-4, 0, 20),
                cv=5,
                max_iter=20000,
                random_state=args.random_state,
            ),
        )
    )
    benchmark_rows.append(
        fit_and_score(
            "elasticnet_reduced",
            train_df,
            test_df,
            REDUCED_NUMERIC_FEATURES,
            ElasticNetCV(
                l1_ratio=[0.1, 0.3, 0.5, 0.7, 0.9],
                alphas=np.logspace(-4, 0, 20),
                cv=5,
                max_iter=20000,
                random_state=args.random_state,
            ),
        )
    )

    balanced_train_df = rebalance_by_floor_area(
        train_df,
        bins=8,
        target_fraction=0.75,
        random_state=args.random_state,
    )
    oversampled_result = fit_and_score(
        "ridge_floor_area_rebalanced",
        balanced_train_df,
        test_df,
        REDUCED_NUMERIC_FEATURES,
        Ridge(alpha=1.0),
    )
    oversampled_result["train_rows_after_rebalance"] = int(len(balanced_train_df))
    benchmark_rows.append(oversampled_result)

    weighted_result = fit_and_score(
        "ridge_floor_area_weighted",
        train_df,
        test_df,
        REDUCED_NUMERIC_FEATURES,
        Ridge(alpha=1.0),
        sample_weight=build_floor_area_sample_weights(
            train_df,
            bins=8,
            target_fraction=0.75,
        ),
    )
    benchmark_rows.append(weighted_result)

    results_df = pd.DataFrame(benchmark_rows).sort_values(["test_rmse_sgd", "test_mae_sgd"])
    results_df.to_csv(output_dir / "benchmark_results.csv", index=False)
    (output_dir / "benchmark_results.json").write_text(results_df.to_json(orient="records", indent=2))

    metadata = {
        "note": (
            "Classic SMOTE is not included because the task is regression with a continuous target. "
            "A floor-area-bin rebalancing baseline is used instead."
        ),
        "vif_pruned_features": vif_pruned_features,
        "anova_k": selector_k,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
    }
    (output_dir / "benchmark_metadata.json").write_text(json.dumps(metadata, indent=2))

    print(results_df.to_string(index=False))
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
