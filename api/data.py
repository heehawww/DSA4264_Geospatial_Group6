from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from hedonic_model.train_hedonic_model import (
    NUMERIC_FEATURES,
    PREDICTIVE_CATEGORICAL_FEATURES,
    add_log_distance,
    engineer_features,
    parse_remaining_lease,
    parse_storey_mid,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_FEATURE_DATASET = DATA_DIR / "resale_flats_with_school_buffer_counts_with_walkability.csv"
OLS_COEFFICIENTS_PATH = DATA_DIR / "ols_coefficients.csv"
METRICS_PATH = DATA_DIR / "metrics.json"
RIDGE_PIPELINE_PATH = DATA_DIR / "ridge_pipeline.pkl"
RDD_RESULTS_PATH = DATA_DIR / "rdd_results.csv"
RDD_SUMMARY_PATH = DATA_DIR / "rdd_summary.json"
PREMIUM_ROWS_PATH = DATA_DIR / "flat_school_premiums_treated_only.csv"
PREMIUM_SUMMARY_PATH = DATA_DIR / "scoring_summary.json"
RAW_RESALE_DATASET_PATH = DATA_DIR / "resale_hdbs_raw.csv"
RAW_RESALE_DATASET_ALTERNATE_PATH = DATA_DIR / "resale_flat_prices.csv"


def _normalise_statsmodels_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in df.columns:
        if column in {"P>|t|", "P>|z|"}:
            rename_map[column] = "p_value"
        elif column == "Coef.":
            rename_map[column] = "coefficient"
        elif column == "Std.Err.":
            rename_map[column] = "std_err"
        elif column == "[0.025":
            rename_map[column] = "ci_lower"
        elif column == "0.975]":
            rename_map[column] = "ci_upper"
        elif column in {"t", "z"}:
            rename_map[column] = "statistic"
    return df.rename(columns=rename_map)


def _safe_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _candidate_raw_dataset_paths() -> list[Path]:
    candidates: list[Path] = []
    if RAW_RESALE_DATASET_PATH.exists():
        candidates.append(RAW_RESALE_DATASET_PATH)
    if RAW_RESALE_DATASET_ALTERNATE_PATH.exists():
        candidates.append(RAW_RESALE_DATASET_ALTERNATE_PATH)
    if candidates:
        return candidates
    return []


@dataclass
class DataStore:
    metrics: dict[str, Any]
    rdd_summary: dict[str, Any]
    premium_summary: dict[str, Any]
    ols_coefficients: pd.DataFrame
    rdd_results: pd.DataFrame
    premium_rows: pd.DataFrame
    feature_dataset: pd.DataFrame
    modeled_feature_dataset: pd.DataFrame
    ridge_pipeline: Any
    defaults: dict[str, Any]
    allowed_categories: dict[str, list[str]]
    raw_dataset_path: Path | None
    raw_dataset: pd.DataFrame | None
    feature_dataset_path: Path
    month_start: pd.Timestamp

    @classmethod
    def load(cls) -> "DataStore":
        feature_dataset_path = DEFAULT_FEATURE_DATASET
        if not feature_dataset_path.exists():
            raise FileNotFoundError(f"Feature dataset not found: {feature_dataset_path}")

        feature_dataset = pd.read_csv(feature_dataset_path)
        modeled_feature_dataset = engineer_features(feature_dataset)
        month_start = modeled_feature_dataset["month_dt"].min()

        ols_coefficients = _normalise_statsmodels_columns(
            pd.read_csv(OLS_COEFFICIENTS_PATH)
        )
        rdd_results = pd.read_csv(RDD_RESULTS_PATH)
        premium_rows = pd.read_csv(PREMIUM_ROWS_PATH)
        metrics = _safe_json(METRICS_PATH)
        rdd_summary = _safe_json(RDD_SUMMARY_PATH)
        premium_summary = _safe_json(PREMIUM_SUMMARY_PATH)
        ridge_pipeline = joblib.load(RIDGE_PIPELINE_PATH)

        raw_dataset_path = next(iter(_candidate_raw_dataset_paths()), None)
        raw_dataset = pd.read_csv(raw_dataset_path) if raw_dataset_path else None

        defaults = cls._build_defaults(feature_dataset, modeled_feature_dataset)
        allowed_categories = {
            "town": sorted(feature_dataset["town"].dropna().astype(str).unique().tolist()),
            "flat_type": sorted(feature_dataset["flat_type"].dropna().astype(str).unique().tolist()),
            "flat_model": sorted(feature_dataset["flat_model"].dropna().astype(str).unique().tolist()),
        }

        return cls(
            metrics=metrics,
            rdd_summary=rdd_summary,
            premium_summary=premium_summary,
            ols_coefficients=ols_coefficients,
            rdd_results=rdd_results,
            premium_rows=premium_rows,
            feature_dataset=feature_dataset,
            modeled_feature_dataset=modeled_feature_dataset,
            ridge_pipeline=ridge_pipeline,
            defaults=defaults,
            allowed_categories=allowed_categories,
            raw_dataset_path=raw_dataset_path,
            raw_dataset=raw_dataset,
            feature_dataset_path=feature_dataset_path,
            month_start=month_start,
        )

    @staticmethod
    def _build_defaults(raw_df: pd.DataFrame, modeled_df: pd.DataFrame) -> dict[str, Any]:
        def median_raw(column: str, fallback: float) -> float:
            if column not in raw_df.columns:
                return fallback
            value = pd.to_numeric(raw_df[column], errors="coerce").median()
            return float(value) if pd.notna(value) else fallback

        def mode_raw(column: str, fallback: str) -> str:
            if column not in raw_df.columns:
                return fallback
            mode = raw_df[column].dropna().astype(str).mode()
            return str(mode.iloc[0]) if not mode.empty else fallback

        month_mode = mode_raw("month", "2025-01")
        lease_commence = int(round(median_raw("lease_commence_date", 1995)))
        remaining_lease_years = median_raw("remaining_lease_years", 70.0)
        remaining_lease = f"{max(int(round(remaining_lease_years)), 1)} years"
        storey_mid = median_raw("storey_mid", 8.0)
        storey_low = max(int(math.floor(storey_mid - 1)), 1)
        storey_high = max(int(math.ceil(storey_mid + 1)), storey_low)
        storey_range = f"{storey_low:02d} TO {storey_high:02d}"

        defaults: dict[str, Any] = {
            "month": month_mode,
            "town": mode_raw("town", "TAMPINES"),
            "flat_type": mode_raw("flat_type", "4 ROOM"),
            "flat_model": mode_raw("flat_model", "Model A"),
            "floor_area_sqm": median_raw("floor_area_sqm", 90.0),
            "lease_commence_date": lease_commence,
            "remaining_lease": remaining_lease,
            "storey_range": storey_range,
            "nearest_mall_walking_distance_m": median_raw("nearest_mall_walking_distance_m", 500.0),
            "malls_within_10min_walk": median_raw("malls_within_10min_walk", 1.0),
            "nearest_mrt_walking_distance_m": median_raw("nearest_mrt_walking_distance_m", 500.0),
            "mrt_unique_lines_within_10min_walk": median_raw("mrt_unique_lines_within_10min_walk", 1.0),
            "school_count_1km": median_raw("school_count_1km", 2.0),
            "good_school_count_1km": median_raw("good_school_count_1km", 0.0),
            "school_count_2km": median_raw("school_count_2km", 5.0),
            "good_school_count_2km": median_raw("good_school_count_2km", 1.0),
            "nearest_bus_stop_walking_distance_m": median_raw("nearest_bus_stop_walking_distance_m", 200.0),
            "bus_stops_within_5min_walk": median_raw("bus_stops_within_5min_walk", 3.0),
            "nearest_hawker_centre_walking_distance_m": median_raw("nearest_hawker_centre_walking_distance_m", 700.0),
            "hawker_centres_within_5min_walk": median_raw("hawker_centres_within_5min_walk", 1.0),
            "nearest_supermarket_walking_distance_m": median_raw("nearest_supermarket_walking_distance_m", 500.0),
            "supermarkets_within_10min_walk": median_raw("supermarkets_within_10min_walk", 1.0),
            "nearest_park_walking_distance_m": median_raw("nearest_park_walking_distance_m", 500.0),
            "parks_within_5min_walk": median_raw("parks_within_5min_walk", 1.0),
            "nearest_pcn_walking_distance_m": median_raw("nearest_pcn_walking_distance_m", 500.0),
            "pcns_within_5min_walk": median_raw("pcns_within_5min_walk", 1.0),
        }

        for column in NUMERIC_FEATURES:
            if column in modeled_df.columns and column not in defaults:
                value = pd.to_numeric(modeled_df[column], errors="coerce").median()
                defaults[column] = float(value) if pd.notna(value) else 0.0

        return defaults

    def dataset_metadata(self) -> dict[str, Any]:
        raw_status = "available" if self.raw_dataset is not None else "missing"
        raw_path = str(self.raw_dataset_path) if self.raw_dataset_path else None
        return {
            "data_dir": str(DATA_DIR),
            "feature_dataset_path": str(self.feature_dataset_path),
            "feature_dataset_rows": int(len(self.feature_dataset)),
            "ols_terms": int(len(self.ols_coefficients)),
            "rdd_rows": int(len(self.rdd_results)),
            "premium_rows": int(len(self.premium_rows)),
            "raw_resale_dataset_status": raw_status,
            "raw_resale_dataset_path": raw_path,
            "raw_resale_dataset_rows": int(len(self.raw_dataset)) if self.raw_dataset is not None else None,
            "raw_resale_dataset_note": (
                "Raw resale CSV is not present in data/. Upload data/resale_hdbs_raw.csv or data/resale_flat_prices.csv for the final API."
                if self.raw_dataset is None
                else f"Raw resale CSV loaded from {raw_path}."
            ),
            "model_metrics": self.metrics,
            "rdd_summary": self.rdd_summary,
            "premium_summary": self.premium_summary,
        }

    def build_prediction_features(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        merged = dict(self.defaults)
        defaulted_fields: list[str] = []

        for key, value in payload.items():
            if value is not None:
                merged[key] = value

        for key in self.defaults:
            if key not in payload or payload.get(key) is None:
                defaulted_fields.append(key)

        month_dt = pd.to_datetime(merged["month"], format="%Y-%m", errors="coerce")
        if pd.isna(month_dt):
            raise ValueError("month must be in YYYY-MM format")

        engineered = {
            "floor_area_sqm": float(merged["floor_area_sqm"]),
            "lease_age_years": float(month_dt.year - float(merged["lease_commence_date"])),
            "remaining_lease_years": float(parse_remaining_lease(merged["remaining_lease"])),
            "storey_mid": float(parse_storey_mid(merged["storey_range"])),
            "sale_year": float(month_dt.year),
            "sale_month": float(month_dt.month),
            "months_since_start": float((month_dt.year - self.month_start.year) * 12 + (month_dt.month - self.month_start.month)),
            "ln_nearest_mall_walking_distance_m": float(add_log_distance(pd.DataFrame([merged]), "nearest_mall_walking_distance_m").iloc[0]),
            "malls_within_10min_walk": float(merged["malls_within_10min_walk"]),
            "ln_nearest_mrt_walking_distance_m": float(add_log_distance(pd.DataFrame([merged]), "nearest_mrt_walking_distance_m").iloc[0]),
            "mrt_unique_lines_within_10min_walk": float(merged["mrt_unique_lines_within_10min_walk"]),
            "school_count_1km": float(merged["school_count_1km"]),
            "good_school_count_1km": float(merged["good_school_count_1km"]),
            "school_count_2km": float(merged["school_count_2km"]),
            "good_school_count_2km": float(merged["good_school_count_2km"]),
            "good_school_within_1km": float(1 if float(merged["good_school_count_1km"]) > 0 else 0),
            "ln_nearest_bus_stop_walking_distance_m": float(add_log_distance(pd.DataFrame([merged]), "nearest_bus_stop_walking_distance_m").iloc[0]),
            "bus_stops_within_5min_walk": float(merged["bus_stops_within_5min_walk"]),
            "ln_nearest_hawker_centre_walking_distance_m": float(add_log_distance(pd.DataFrame([merged]), "nearest_hawker_centre_walking_distance_m").iloc[0]),
            "hawker_centres_within_5min_walk": float(merged["hawker_centres_within_5min_walk"]),
            "ln_nearest_supermarket_walking_distance_m": float(add_log_distance(pd.DataFrame([merged]), "nearest_supermarket_walking_distance_m").iloc[0]),
            "supermarkets_within_10min_walk": float(merged["supermarkets_within_10min_walk"]),
            "ln_nearest_park_walking_distance_m": float(add_log_distance(pd.DataFrame([merged]), "nearest_park_walking_distance_m").iloc[0]),
            "parks_within_5min_walk": float(merged["parks_within_5min_walk"]),
            "ln_nearest_pcn_walking_distance_m": float(add_log_distance(pd.DataFrame([merged]), "nearest_pcn_walking_distance_m").iloc[0]),
            "pcns_within_5min_walk": float(merged["pcns_within_5min_walk"]),
            "town": str(merged["town"]),
            "flat_type": str(merged["flat_type"]),
            "flat_model": str(merged["flat_model"]),
        }

        if math.isnan(engineered["remaining_lease_years"]):
            raise ValueError("remaining_lease could not be parsed")
        if math.isnan(engineered["storey_mid"]):
            raise ValueError("storey_range could not be parsed")

        return engineered, defaulted_fields


store = DataStore.load()
