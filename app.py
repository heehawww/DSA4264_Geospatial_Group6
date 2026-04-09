from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv

import chatbot.agent as chatbot_agent
from hedonic_model.train_hedonic_model import (
    FEATURE_SPECS,
    engineer_features,
    fit_predictive_model,
    time_split,
)


REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

FEATURES_PATH_CANDIDATES = [
    REPO_ROOT / "data/resale_flats_with_school_buffer_counts_with_walkability.csv",
    REPO_ROOT / "walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv",
]
RIDGE_PIPELINE_PATH_CANDIDATES = [
    REPO_ROOT / "data/ridge_pipeline.pkl",
    REPO_ROOT / "hedonic_model/outputs/ridge_pipeline.pkl",
]
METRICS_PATH_CANDIDATES = [
    REPO_ROOT / "data/metrics.json",
    REPO_ROOT / "hedonic_model/outputs/metrics.json",
]
POINTS_PATH = REPO_ROOT / "primary_boundaries/outputs/resale_address_points_matched_with_school_counts.geojson"
BUFFER_1KM_PATH = REPO_ROOT / "primary_boundaries/outputs/primary_school_boundaries_buffer_1km.geojson"
BUFFER_2KM_PATH = REPO_ROOT / "primary_boundaries/outputs/primary_school_boundaries_buffer_2km.geojson"
BUILDINGS_PATH = REPO_ROOT / "primary_boundaries/outputs/hdb_existing_buildings_layer.geojson"
DEFAULT_API_BASE_URL = os.getenv("HDB_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


st.set_page_config(
    page_title="HDB Hedonic Explorer",
    page_icon=":world_map:",
    layout="wide",
)

st.markdown(
    """
    <style>
    div[data-testid="stChatMessage"] {
        max-width: 100%;
        overflow-wrap: break-word;
        word-break: normal;
    }

    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] li,
    div[data-testid="stChatMessage"] span {
        overflow-wrap: break-word;
        word-break: normal;
        white-space: normal;
    }

    div[data-testid="stChatMessage"] a {
        overflow-wrap: anywhere;
        word-break: break-word;
    }

    div[data-testid="stChatMessage"] pre,
    div[data-testid="stChatMessage"] code {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        word-break: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _format_currency(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"S${value:,.0f}"


def _render_chat_text(text: str) -> None:
    st.markdown(text.replace("$", r"\$"))


def _escape_tooltip_value(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _to_pydeck_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    def normalize_value(value: Any) -> Any:
        if isinstance(value, (list, dict, tuple)):
            return value
        if pd.isna(value):
            return None
        if isinstance(value, np.generic):
            return value.item()
        return value

    normalized = frame.copy()
    for column in normalized.columns:
        normalized[column] = normalized[column].map(normalize_value)
    return normalized.to_dict(orient="records")


def _get_selected_school_name() -> str | None:
    selection_state = st.session_state.get("prediction_map", {})
    selected_objects = selection_state.get("selection", {}).get("objects", {}).get("school_points", [])
    if not selected_objects:
        return None
    return selected_objects[0].get("school_name")


def _resolve_first_existing_path(candidates: list[Path], label: str) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    candidate_text = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(f"Could not find {label}. Checked:\n{candidate_text}")


def _find_first_existing_path(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


class ApiClientError(RuntimeError):
    pass


def _normalise_api_params(params: dict[str, Any]) -> dict[str, Any]:
    clean_params: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        clean_params[key] = value
    return clean_params


def api_get(path: str, params: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    url = f"{DEFAULT_API_BASE_URL}{path}"
    try:
        response = requests.get(
            url,
            params=_normalise_api_params(params or {}),
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ApiClientError(f"Could not reach API endpoint {url}: {exc}") from exc
    return response.json()


@st.cache_data(show_spinner=False, ttl=30)
def get_api_health() -> dict[str, Any]:
    return api_get("/health", timeout=5)


def collect_api_context(user_prompt: str) -> dict[str, Any]:
    prompt = user_prompt.lower()
    context: dict[str, Any] = {
        "api_base_url": DEFAULT_API_BASE_URL,
    }

    context["metadata"] = api_get("/metadata")
    context["resales_summary"] = api_get("/resales/summary")

    if any(word in prompt for word in ["premium", "good school", "school", "1km"]):
        context["premium_summary"] = api_get("/town-premiums/summary")
        context["premium_rows_sample"] = api_get("/town-premiums", {"limit": 10})

    if any(word in prompt for word in ["predict", "prediction", "what if", "hypothetical"]):
        context["prediction_schema"] = api_get("/predict/schema")

    return context


def render_api_status() -> None:
    st.subheader("Chatbot service")
    st.caption(f"API base URL: `{DEFAULT_API_BASE_URL}`")
    if os.getenv("OPENAI_API_KEY"):
        st.success("Agent key loaded from environment.")
    else:
        st.warning("OPENAI_API_KEY is not loaded. Add it to the repo-root `.env` file.")
    try:
        health = get_api_health()
    except ApiClientError:
        st.warning("API offline. Start FastAPI to enable service-backed chat.")
        st.code("uvicorn api.main:app --reload", language="bash")
        return
    st.success(f"Connected: {health.get('status', 'ok')}")


@st.cache_data(show_spinner=False)
def load_model_metrics() -> dict[str, Any]:
    metrics_path = _find_first_existing_path(METRICS_PATH_CANDIDATES)
    if metrics_path is None:
        return {}
    try:
        return json.loads(metrics_path.read_text())
    except json.JSONDecodeError:
        return {}


def _feature_spec_from_metrics() -> str:
    metrics = load_model_metrics()
    feature_spec = str(metrics.get("feature_spec", "baseline"))
    return feature_spec if feature_spec in FEATURE_SPECS else "baseline"


def _get_pipeline_feature_columns(predictive_model: Any) -> list[str]:
    preprocessor = predictive_model.named_steps["preprocessor"]
    numeric_columns = list(preprocessor.transformers_[0][2])
    categorical_columns = list(preprocessor.transformers_[1][2])
    return numeric_columns + categorical_columns


@st.cache_data(show_spinner=False)
def load_prediction_dataset() -> pd.DataFrame:
    raw = pd.read_csv(_resolve_first_existing_path(FEATURES_PATH_CANDIDATES, "feature dataset"))
    fallback_numeric_features = FEATURE_SPECS[_feature_spec_from_metrics()]
    model_df = engineer_features(raw, numeric_features=fallback_numeric_features)
    predictive_model = load_or_fit_predictive_model(model_df)
    model_feature_columns = _get_pipeline_feature_columns(predictive_model)
    numeric_columns = [column for column in model_feature_columns if column in FEATURE_SPECS["baseline"]]
    model_df = engineer_features(raw, numeric_features=numeric_columns)
    _, test_df = time_split(model_df, test_months=12)
    predictions = build_prediction_frame_for_app(raw, model_df, predictive_model, test_df, model_feature_columns)

    predictions["month"] = predictions["month"].astype(str)
    predictions["dataset_split"] = predictions["dataset_split"].astype(str)
    predictions["good_school_within_1km"] = (
        pd.to_numeric(predictions["good_school_within_1km"], errors="coerce").fillna(0).astype(int)
    )
    predictions["resale_price"] = pd.to_numeric(predictions["resale_price"], errors="coerce")
    predictions["predicted_resale_price"] = pd.to_numeric(
        predictions["predicted_resale_price"],
        errors="coerce",
    )
    predictions["prediction_error"] = pd.to_numeric(predictions["prediction_error"], errors="coerce")
    predictions["month_dt"] = pd.to_datetime(predictions["month"], format="%Y-%m", errors="coerce")
    return predictions


@st.cache_resource(show_spinner=False)
def load_or_fit_predictive_model(model_df: pd.DataFrame):
    pipeline_path = None
    for candidate in RIDGE_PIPELINE_PATH_CANDIDATES:
        if candidate.exists():
            pipeline_path = candidate
            break

    if pipeline_path is not None:
        return joblib.load(pipeline_path)

    numeric_features = FEATURE_SPECS[_feature_spec_from_metrics()]
    if model_df.empty:
        raise ValueError("Model feature dataset is empty.")
    train_df, test_df = time_split(model_df, test_months=12)
    predictive_model, _, _ = fit_predictive_model(train_df, test_df, numeric_features=numeric_features)
    return predictive_model


def build_prediction_frame_for_app(
    raw_df: pd.DataFrame,
    model_df: pd.DataFrame,
    predictive_model: Any,
    test_df: pd.DataFrame,
    model_feature_columns: list[str],
) -> pd.DataFrame:
    """Build frontend prediction rows from the saved ridge pipeline and feature table."""
    X_all = model_df[model_feature_columns]
    predicted_prices = np.exp(predictive_model.predict(X_all))

    keep_columns = [
        "address_key",
        "month",
        "town",
        "flat_type",
        "flat_model",
        "block",
        "street_name",
        "storey_range",
        "floor_area_sqm",
        "lease_commence_date",
        "remaining_lease",
        "resale_price",
        "school_count_1km",
        "good_school_count_1km",
        "school_count_2km",
        "good_school_count_2km",
    ]
    predictions = raw_df.loc[model_df.index, keep_columns].copy()
    predictions["predicted_resale_price"] = predicted_prices
    predictions["prediction_error"] = predictions["resale_price"] - predictions["predicted_resale_price"]
    predictions["good_school_within_1km"] = model_df["good_school_within_1km"].to_numpy()
    predictions["dataset_split"] = np.where(predictions.index.isin(test_df.index), "test", "train")
    return predictions.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_points() -> pd.DataFrame:
    points = gpd.read_file(POINTS_PATH)[["address_key", "latitude", "longitude"]].copy()
    points["latitude"] = pd.to_numeric(points["latitude"], errors="coerce")
    points["longitude"] = pd.to_numeric(points["longitude"], errors="coerce")
    return points.dropna(subset=["latitude", "longitude"]).drop_duplicates("address_key")


@st.cache_data(show_spinner=False)
def load_school_buffers(buffer_distance_km: int) -> dict[str, Any]:
    buffer_path = BUFFER_1KM_PATH if buffer_distance_km == 1 else BUFFER_2KM_PATH
    buffers = gpd.read_file(buffer_path)
    if buffers.crs and buffers.crs.to_string() != "EPSG:4326":
        buffers = buffers.to_crs(4326)
    buffers["school_level_label"] = buffers["school_tier"].fillna("Unknown")
    buffers["buffer_label"] = f"{buffer_distance_km}km boundary"
    buffers["school_estates_label"] = buffers[f"estates_within_{buffer_distance_km}km"].fillna("No estate list available")
    buffers["tooltip_html"] = buffers.apply(
        lambda row: (
            f"<b>{_escape_tooltip_value(row['school_name'])}</b><br/>"
            f"{_escape_tooltip_value(row['buffer_label'])}<br/>"
            f"Tier: {_escape_tooltip_value(row['school_level_label'])}<br/>"
            f"Covered estates: {_escape_tooltip_value(row['school_estates_label'])}"
        ),
        axis=1,
    )
    return json.loads(buffers.to_json())


def filter_school_buffers(buffer_distance_km: int, school_name: str) -> dict[str, Any]:
    buffers = load_school_buffers(buffer_distance_km)
    if not school_name:
        return buffers
    filtered_features = [
        feature
        for feature in buffers.get("features", [])
        if feature.get("properties", {}).get("school_name") == school_name
    ]
    return {
        **buffers,
        "features": filtered_features,
    }


@st.cache_data(show_spinner=False)
def load_school_points() -> list[dict[str, Any]]:
    schools = gpd.read_file(BUFFER_1KM_PATH)[
        ["school_name", "is_good_school", "school_tier", "geometry"]
    ].copy()
    if schools.crs and schools.crs.to_string() != "EPSG:4326":
        schools = schools.to_crs(4326)
    school_points = schools.geometry.representative_point()
    schools["latitude"] = school_points.y
    schools["longitude"] = school_points.x
    schools = schools.dropna(subset=["latitude", "longitude"]).drop_duplicates("school_name")
    school_mask = schools["is_good_school"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
    schools["point_color"] = school_mask.map(
        lambda is_good: [34, 139, 34, 220] if is_good else [180, 110, 35, 220]
    )
    schools["school_type_label"] = school_mask.map(
        lambda is_good: "Good school" if is_good else "Other primary school"
    )
    schools["school_tier"] = schools["school_tier"].fillna("Unknown")
    schools["tooltip_html"] = schools.apply(
        lambda row: (
            f"<b>{_escape_tooltip_value(row['school_name'])}</b><br/>"
            f"Tier: {_escape_tooltip_value(row['school_tier'])}"
        ),
        axis=1,
    )
    return _to_pydeck_records(
        schools[
            [
                "school_name",
                "school_tier",
                "latitude",
                "longitude",
                "point_color",
                "school_type_label",
                "tooltip_html",
            ]
        ]
    )


@st.cache_data(show_spinner=False)
def load_hdb_buildings() -> dict[str, Any]:
    buildings = gpd.read_file(BUILDINGS_PATH)
    if buildings.crs and buildings.crs.to_string() != "EPSG:4326":
        buildings = buildings.to_crs(4326)
    buildings["building_avg_price_label"] = (
        pd.to_numeric(buildings["mean_avg_resale_price"], errors="coerce")
        .map(lambda value: _format_currency(value) if pd.notna(value) else "N/A")
    )
    buildings["tooltip_html"] = buildings.apply(
        lambda row: (
            f"<b>HDB Block {_escape_tooltip_value(row['BLK_NO'])}</b><br/>"
            f"Average resale price: {_escape_tooltip_value(row['building_avg_price_label'])}"
        ),
        axis=1,
    )
    return json.loads(buildings.to_json())


@st.cache_data(show_spinner=False)
def load_good_school_lookup() -> pd.DataFrame:
    points = gpd.read_file(POINTS_PATH)[["address_key", "geometry"]].copy()
    buffers = gpd.read_file(BUFFER_1KM_PATH)[["school_name", "is_good_school", "geometry"]].copy()
    good_mask = buffers["is_good_school"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
    buffers = buffers.loc[good_mask].copy()
    joined = gpd.sjoin(
        points,
        buffers,
        how="left",
        predicate="within",
    )
    lookup = (
        joined.groupby("address_key")["school_name"]
        .apply(lambda series: ", ".join(sorted({str(value) for value in series.dropna() if str(value).strip()})))
        .reset_index(name="good_school_names_1km")
    )
    return lookup


@st.cache_data(show_spinner=False)
def load_school_rdd_premium_lookup() -> dict[str, float]:
    rdd_path = REPO_ROOT / "data/school_specific_rdd_results.csv"
    if not rdd_path.exists():
        return {}
    rdd = pd.read_csv(rdd_path)
    filtered = rdd.loc[
        (rdd["specification"].astype(str).str.strip().str.lower() == "controlled")
        & (pd.to_numeric(rdd["bandwidth_m"], errors="coerce") == 100)
    ].copy()
    filtered["boundary_school_name"] = filtered["boundary_school_name"].astype(str).str.strip().str.upper()
    filtered["cutoff_premium_pct"] = pd.to_numeric(filtered["cutoff_premium_pct"], errors="coerce")
    filtered = filtered.dropna(subset=["boundary_school_name", "cutoff_premium_pct"])
    return dict(zip(filtered["boundary_school_name"], filtered["cutoff_premium_pct"], strict=False))


def _estimate_rdd_premium_pct(good_school_names: object, school_rdd_lookup: dict[str, float]) -> float:
    if not isinstance(good_school_names, str) or not good_school_names.strip():
        return np.nan
    matched_premiums = [
        school_rdd_lookup[name.strip().upper()]
        for name in good_school_names.split(",")
        if name.strip().upper() in school_rdd_lookup
    ]
    if not matched_premiums:
        return np.nan
    return float(np.mean(matched_premiums))


@st.cache_data(show_spinner=False)
def build_map_dataset() -> pd.DataFrame:
    predictions = load_prediction_dataset()
    points = load_points()
    merged = predictions.merge(points, on="address_key", how="left")
    merged = merged.merge(load_good_school_lookup(), on="address_key", how="left")
    merged = merged.dropna(subset=["latitude", "longitude", "predicted_resale_price"])
    actual_prices = pd.to_numeric(merged["resale_price"], errors="coerce")
    predicted_prices = pd.to_numeric(merged["predicted_resale_price"], errors="coerce")
    merged["display_price"] = actual_prices.fillna(predicted_prices)
    merged["display_price_type"] = np.where(actual_prices.notna(), "Price", "Predicted price")
    merged["price_gap_pct"] = merged["prediction_error"] / merged["predicted_resale_price"]
    school_rdd_lookup = load_school_rdd_premium_lookup()
    merged["school_rdd_premium_pct"] = merged["good_school_names_1km"].map(
        lambda value: _estimate_rdd_premium_pct(value, school_rdd_lookup)
    )
    merged["premium_price"] = merged["predicted_resale_price"] * merged["school_rdd_premium_pct"]
    return merged


def filter_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    months = sorted(dataset["month"].dropna().unique().tolist())

    st.sidebar.header("Filters")
    selected_month = st.sidebar.selectbox("Month", months, index=len(months) - 1)
    split = st.sidebar.selectbox("Dataset split", ["all", "train", "test"])
    school_filter = st.sidebar.selectbox("Good school within 1km", ["all", "yes", "no"])
    show_buildings = st.sidebar.toggle("Show HDB building outlines", value=True)

    filtered = dataset.loc[dataset["month"] == selected_month].copy()
    if split != "all":
        filtered = filtered.loc[filtered["dataset_split"] == split].copy()
    if school_filter == "yes":
        filtered = filtered.loc[filtered["good_school_within_1km"] == 1].copy()
    elif school_filter == "no":
        filtered = filtered.loc[filtered["good_school_within_1km"] == 0].copy()

    st.session_state["active_filters"] = {
        "month": selected_month,
        "split": split,
        "school_filter": school_filter,
        "metric": "display_price",
        "show_buildings": show_buildings,
    }
    return filtered


def add_color_columns(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    colored = frame.copy()
    metric_values = pd.to_numeric(colored["premium_price"], errors="coerce")
    colored["has_flat_premium"] = metric_values.notna()
    colored["fill_color"] = colored["has_flat_premium"].map(
        lambda has_premium: [214, 51, 132, 220] if has_premium else [244, 182, 213, 150]
    )
    colored["radius"] = 28
    return colored


def render_map_legend() -> None:
    st.markdown(
        """
        <div style="display:flex; gap:20px; flex-wrap:wrap; align-items:center; margin:0.25rem 0 0.75rem 0; font-size:0.92rem;">
          <span><span style="display:inline-block; width:12px; height:12px; border-radius:999px; background:#d63384; margin-right:6px; border:1px solid rgba(0,0,0,0.15);"></span>Flat premium: yes</span>
          <span><span style="display:inline-block; width:12px; height:12px; border-radius:999px; background:#f4b6d5; margin-right:6px; border:1px solid rgba(0,0,0,0.15);"></span>Flat premium: no</span>
          <span><span style="display:inline-block; width:12px; height:12px; border-radius:999px; background:#228b22; margin-right:6px; border:1px solid rgba(0,0,0,0.15);"></span>Good school</span>
          <span><span style="display:inline-block; width:12px; height:12px; border-radius:999px; background:#b46e23; margin-right:6px; border:1px solid rgba(0,0,0,0.15);"></span>Other school</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_map(
    filtered: pd.DataFrame,
    metric: str,
    show_buildings: bool,
) -> None:
    if filtered.empty:
        st.warning("No rows match the current filters.")
        return

    points = add_color_columns(filtered, metric)
    points["display_price_label"] = points["display_price"].map(_format_currency)
    points["premium_price_label"] = points["premium_price"].map(_format_currency)
    points["good_school_names_1km"] = (
        points["good_school_names_1km"]
        .fillna("")
        .replace("", "None")
    )
    points["tooltip_html"] = points.apply(
        lambda row: (
            f"<b>{_escape_tooltip_value(row['block'])} {_escape_tooltip_value(row['street_name'])}</b><br/>"
            f"{_escape_tooltip_value(row['display_price_type'])}: "
            f"{_escape_tooltip_value(row['display_price_label'])}<br/>"
            f"Premium price: {_escape_tooltip_value(row['premium_price_label'])}<br/>"
            f"Good school(s) within 1km: {_escape_tooltip_value(row['good_school_names_1km'])}"
        ),
        axis=1,
    )
    if len(points) > 12000:
        points = points.sample(12000, random_state=42)
    point_records = _to_pydeck_records(points)

    tooltip = {"html": "{tooltip_html}"}

    selected_school_name = _get_selected_school_name()

    layers: list[pdk.Layer] = []
    if selected_school_name:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                filter_school_buffers(2, selected_school_name),
                id="school_boundary_2km",
                stroked=True,
                filled=True,
                get_fill_color=[121, 169, 237, 18],
                get_line_color=[54, 98, 178, 150],
                line_width_min_pixels=1,
                pickable=True,
                auto_highlight=True,
            )
        )
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                filter_school_buffers(1, selected_school_name),
                id="school_boundary_1km",
                stroked=True,
                filled=True,
                get_fill_color=[247, 201, 72, 32],
                get_line_color=[176, 132, 0, 170],
                line_width_min_pixels=2,
                pickable=True,
                auto_highlight=True,
            )
        )
    layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=load_school_points(),
                id="school_points",
            get_position="[longitude, latitude]",
            get_fill_color="point_color",
            get_radius=45,
            pickable=True,
            opacity=0.95,
            stroked=True,
            get_line_color=[255, 255, 255, 220],
            line_width_min_pixels=1,
        )
    )
    if show_buildings:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                load_hdb_buildings(),
                id="hdb_buildings",
                stroked=True,
                filled=False,
                get_line_color=[66, 66, 66, 90],
                line_width_min_pixels=1,
                pickable=True,
                auto_highlight=True,
            )
        )
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=point_records,
            id="resale_flats",
            get_position="[longitude, latitude]",
            get_fill_color="fill_color",
            get_radius="radius",
            pickable=True,
            opacity=0.7,
            stroked=False,
        )
    )

    view_state = pdk.ViewState(
        latitude=float(points["latitude"].median()),
        longitude=float(points["longitude"].median()),
        zoom=10.7,
        pitch=0,
    )
    st.pydeck_chart(
        pdk.Deck(
            map_provider="carto",
            map_style=pdk.map_styles.LIGHT,
            initial_view_state=view_state,
            layers=layers,
            tooltip=tooltip,
        ),
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-object",
        key="prediction_map",
    )


def build_summary_context(filtered: pd.DataFrame) -> str:
    summary = filtered.copy()
    top_towns = (
        summary.groupby("town", as_index=False)
        .agg(
            listings=("address_key", "size"),
            avg_predicted=("predicted_resale_price", "mean"),
            avg_actual=("resale_price", "mean"),
            avg_error=("prediction_error", "mean"),
            near_good_school_share=("good_school_within_1km", "mean"),
        )
        .sort_values(["avg_predicted", "listings"], ascending=[False, False])
        .head(8)
    )
    school_effect = (
        summary.groupby("good_school_within_1km", as_index=False)
        .agg(
            listings=("address_key", "size"),
            avg_predicted=("predicted_resale_price", "mean"),
            avg_actual=("resale_price", "mean"),
            avg_error=("prediction_error", "mean"),
        )
        .to_dict(orient="records")
    )

    filters = st.session_state.get("active_filters", {})
    context = {
        "active_filters": filters,
        "rows": int(len(summary)),
        "town_count": int(summary["town"].nunique()),
        "avg_predicted_resale_price": float(summary["predicted_resale_price"].mean()),
        "median_predicted_resale_price": float(summary["predicted_resale_price"].median()),
        "avg_actual_resale_price": float(summary["resale_price"].mean()),
        "mean_prediction_error": float(summary["prediction_error"].mean()),
        "mean_absolute_prediction_error": float(summary["prediction_error"].abs().mean()),
        "good_school_share": float(summary["good_school_within_1km"].mean()),
        "top_towns": top_towns.to_dict(orient="records"),
        "school_exposure_comparison": school_effect,
    }
    return json.dumps(context, indent=2)


def fallback_chat_response(
    filtered: pd.DataFrame,
    user_prompt: str,
    api_context: dict[str, Any] | None = None,
) -> str:
    if api_context and "resales_summary" in api_context:
        summary = api_context["resales_summary"].get("summary", {})
        count = summary.get("count", 0)
        median_price = summary.get("median_resale_price")
        mean_price = summary.get("mean_resale_price")
        return (
            "From the API-backed resale summary across the dataset, "
            f"I found {count:,} resale records. The mean resale price is "
            f"{_format_currency(mean_price)} and the median is {_format_currency(median_price)}. "
            "Install `pydantic-ai` and set `OPENAI_API_KEY` for a fuller agent-style explanation."
        )

    if filtered.empty:
        return "There are no prediction rows in the current filter, so I cannot summarize findings yet."

    average_predicted = filtered["predicted_resale_price"].mean()
    average_actual = filtered["resale_price"].mean()
    school_yes = filtered.loc[filtered["good_school_within_1km"] == 1, "predicted_resale_price"]
    school_no = filtered.loc[filtered["good_school_within_1km"] == 0, "predicted_resale_price"]
    school_sentence = ""
    if not school_yes.empty and not school_no.empty:
        premium = school_yes.mean() - school_no.mean()
        school_sentence = (
            f" Listings within 1km of a good school have an average predicted price that is "
            f"{_format_currency(abs(premium))} {'higher' if premium >= 0 else 'lower'} than the rest."
        )

    town_lookup = {town.upper(): town for town in filtered["town"].dropna().unique()}
    requested_towns = [town for key, town in town_lookup.items() if key in user_prompt.upper()]
    if requested_towns:
        town_frame = filtered.loc[filtered["town"].isin(requested_towns)]
        town_avg = town_frame.groupby("town")["predicted_resale_price"].mean().sort_values(ascending=False)
        town_lines = ", ".join(f"{town} at {_format_currency(value)}" for town, value in town_avg.items())
        return (
            f"For the current filter, the model predicts an average resale price of {_format_currency(average_predicted)}, "
            f"versus an actual average of {_format_currency(average_actual)}.{school_sentence} "
            f"Among the towns you mentioned, the predicted averages are: {town_lines}."
        )

    top_town = (
        filtered.groupby("town")["predicted_resale_price"]
        .mean()
        .sort_values(ascending=False)
        .head(1)
    )
    top_town_text = ""
    if not top_town.empty:
        top_town_text = f" {top_town.index[0]} has the highest average predicted price at {_format_currency(top_town.iloc[0])}."

    return (
        f"For the current map selection, the model predicts an average resale price of {_format_currency(average_predicted)} "
        f"across {len(filtered):,} transactions, compared with an actual average of {_format_currency(average_actual)}."
        f"{school_sentence}{top_town_text} "
        "Install `pydantic-ai` and set `OPENAI_API_KEY` to turn this into a full agent response."
    )


def call_agent_with_context(
    map_context: str,
    api_context: dict[str, Any],
    conversation: list[dict[str, str]],
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not loaded. Put it in "
            f"{REPO_ROOT / '.env'} and restart Streamlit."
        )
    user_prompt = conversation[-1]["content"]
    return chatbot_agent.run_hdb_agent(
        user_prompt,
        map_context=map_context,
        api_status=api_context,
        conversation=conversation,
        api_base_url=DEFAULT_API_BASE_URL,
    )


def render_chatbot(filtered: pd.DataFrame) -> None:
    st.subheader("HDB price assistant")
    st.caption(
        "Ask plain-language questions about resale prices, towns, school access, or what-if price estimates."
    )

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "I can help compare resale prices, towns, school access, and what-if price estimates. "
                    "The map filters only affect the map unless you ask about the current map."
                ),
            }
        ]

    message_area = st.container(height=560, border=True)
    with message_area:
        for message in st.session_state["chat_messages"]:
            with st.chat_message(message["role"]):
                _render_chat_text(message["content"])

    user_prompt = st.chat_input("Ask about prices, towns, school access, or a what-if estimate")
    if not user_prompt:
        return

    st.session_state["chat_messages"].append({"role": "user", "content": user_prompt})

    with st.spinner("Gathering map and API context..."):
        map_context = build_summary_context(filtered)
        api_context: dict[str, Any] = {}
        try:
            api_context = collect_api_context(user_prompt)
        except ApiClientError as exc:
            api_context = {"api_error": str(exc), "api_base_url": DEFAULT_API_BASE_URL}

        try:
            reply = call_agent_with_context(
                map_context,
                api_context,
                st.session_state["chat_messages"],
            )
        except Exception as exc:
            reply = fallback_chat_response(filtered, user_prompt, api_context)
            if "api_error" not in api_context:
                reply = f"{reply}\n\nAgent call failed: {exc}"
    st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
    st.rerun()


def main() -> None:
    st.title("HDB Hedonic Model Explorer")
    st.caption(
        "Explore model-predicted resale prices on the map and ask natural-language questions about the active filter."
    )

    dataset = build_map_dataset()
    filtered = filter_dataset(dataset)
    filters = st.session_state["active_filters"]

    map_tab, chat_tab = st.tabs(["Map", "Chatbot"])

    with map_tab:
        st.subheader("Prediction map")
        st.caption(
            f"Showing {len(filtered):,} resale-flat records for {filters['month']}. "
            "Hover a unit to see actual resale price when available, otherwise predicted price. "
            "Click a school dot to reveal that school's 1km and 2km boundaries."
        )
        render_map_legend()
        render_map(
            filtered,
            filters["metric"],
            filters["show_buildings"],
        )

    with chat_tab:
        render_api_status()
        st.divider()
        render_chatbot(filtered)


if __name__ == "__main__":
    main()
