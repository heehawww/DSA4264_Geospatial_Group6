from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv

import chatbot.agent as chatbot_agent
from hedonic_model.train_hedonic_model import (
    engineer_features,
    fit_predictive_model,
    time_split,
)


REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")
chatbot_agent = importlib.reload(chatbot_agent)

PREDICTIONS_PATH = REPO_ROOT / "hedonic_model/outputs/predictions.csv"
FEATURES_PATH = (
    REPO_ROOT
    / "data/feature_engineering/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv"
)
POINTS_PATH = REPO_ROOT / "data/feature_engineering/outputs/resale_address_points_matched_with_school_counts.geojson"
BUFFER_1KM_PATH = REPO_ROOT / "data/feature_engineering/outputs/primary_school_boundaries_buffer_1km.geojson"
BUFFER_2KM_PATH = REPO_ROOT / "data/feature_engineering/outputs/primary_school_boundaries_buffer_2km.geojson"
BUILDINGS_PATH = REPO_ROOT / "data/feature_engineering/outputs/hdb_existing_buildings_layer.geojson"
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
def load_prediction_dataset() -> pd.DataFrame:
    if PREDICTIONS_PATH.exists():
        predictions = pd.read_csv(PREDICTIONS_PATH)
    else:
        raw = pd.read_csv(FEATURES_PATH)
        model_df = engineer_features(raw)
        train_df, test_df = time_split(model_df, test_months=12)
        predictive_model, _, _ = fit_predictive_model(train_df, test_df)
        predictions = build_prediction_frame_for_app(raw, model_df, predictive_model, test_df)

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


def build_prediction_frame_for_app(
    raw_df: pd.DataFrame,
    model_df: pd.DataFrame,
    predictive_model: Any,
    test_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build frontend prediction rows if the training export has not been generated yet."""
    feature_columns = [
        column
        for column in model_df.columns
        if column not in {"log_resale_price", "resale_price", "month_dt", "month_period"}
    ]
    X_all = model_df[feature_columns]
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
            f"Matched transactions: {_escape_tooltip_value(row['matched_txn_count'])}<br/>"
            f"Average resale price: {_escape_tooltip_value(row['building_avg_price_label'])}"
        ),
        axis=1,
    )
    return json.loads(buildings.to_json())


@st.cache_data(show_spinner=False)
def build_map_dataset() -> pd.DataFrame:
    predictions = load_prediction_dataset()
    points = load_points()
    merged = predictions.merge(points, on="address_key", how="left")
    merged = merged.dropna(subset=["latitude", "longitude", "predicted_resale_price"])
    merged["price_gap_pct"] = merged["prediction_error"] / merged["predicted_resale_price"]
    return merged


def filter_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    months = sorted(dataset["month"].dropna().unique().tolist())

    st.sidebar.header("Filters")
    selected_month = st.sidebar.selectbox("Month", months, index=len(months) - 1)
    split = st.sidebar.selectbox("Dataset split", ["all", "train", "test"])
    school_filter = st.sidebar.selectbox("Good school within 1km", ["all", "yes", "no"])
    metric = st.sidebar.selectbox(
        "Map color metric",
        [
            "predicted_resale_price",
            "prediction_error",
            "resale_price",
            "good_school_count_1km",
        ],
    )
    show_school_1km = st.sidebar.toggle("Show school 1km boundaries", value=True)
    show_school_2km = st.sidebar.toggle("Show school 2km boundaries", value=True)
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
        "metric": metric,
        "show_school_1km": show_school_1km,
        "show_school_2km": show_school_2km,
        "show_buildings": show_buildings,
    }
    return filtered


def add_color_columns(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    colored = frame.copy()
    metric_values = pd.to_numeric(colored[metric], errors="coerce").fillna(0)
    if metric == "prediction_error":
        max_abs = max(metric_values.abs().quantile(0.95), 1)
        clipped = metric_values.clip(-max_abs, max_abs) / max_abs
        colored["fill_color"] = clipped.apply(
            lambda value: [35, 109, 177, 180] if value >= 0 else [214, 69, 65, 180]
        )
        colored["radius"] = 75 + metric_values.abs().clip(0, max_abs).fillna(0) / max_abs * 125
    else:
        high = max(metric_values.quantile(0.95), 1)
        scaled = metric_values.clip(0, high) / high
        colored["fill_color"] = scaled.apply(
            lambda value: [
                int(34 + value * 180),
                int(82 + value * 90),
                int(46 + value * 40),
                180,
            ]
        )
        colored["radius"] = 70 + scaled * 140
    return colored


def render_map(
    filtered: pd.DataFrame,
    metric: str,
    show_school_1km: bool,
    show_school_2km: bool,
    show_buildings: bool,
) -> None:
    if filtered.empty:
        st.warning("No rows match the current filters.")
        return

    points = add_color_columns(filtered, metric)
    actual_prices = pd.to_numeric(points["resale_price"], errors="coerce")
    predicted_prices = pd.to_numeric(points["predicted_resale_price"], errors="coerce")
    points["display_price"] = actual_prices.fillna(predicted_prices)
    points["display_price_type"] = actual_prices.notna().map(
        {True: "Actual resale price", False: "Predicted price"}
    )
    points["display_price_label"] = points["display_price"].map(_format_currency)
    points["actual_price_label"] = points["resale_price"].map(_format_currency)
    points["predicted_price_label"] = points["predicted_resale_price"].map(_format_currency)
    points["prediction_error_label"] = points["prediction_error"].map(_format_currency)
    points["school_count_1km_label"] = points["good_school_count_1km"].fillna(0).astype(int).astype(str)
    points["tooltip_html"] = points.apply(
        lambda row: (
            f"<b>{_escape_tooltip_value(row['block'])} {_escape_tooltip_value(row['street_name'])}</b><br/>"
            f"{_escape_tooltip_value(row['display_price_type'])}: "
            f"{_escape_tooltip_value(row['display_price_label'])}<br/>"
            f"Predicted: {_escape_tooltip_value(row['predicted_price_label'])}<br/>"
            f"Actual: {_escape_tooltip_value(row['actual_price_label'])}<br/>"
            f"Error: {_escape_tooltip_value(row['prediction_error_label'])}<br/>"
            f"Good schools within 1km: {_escape_tooltip_value(row['school_count_1km_label'])}"
        ),
        axis=1,
    )
    if len(points) > 12000:
        points = points.sample(12000, random_state=42)

    tooltip = {"html": "{tooltip_html}"}

    layers: list[pdk.Layer] = []
    if show_school_2km:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                load_school_buffers(2),
                stroked=True,
                filled=True,
                get_fill_color=[121, 169, 237, 18],
                get_line_color=[54, 98, 178, 150],
                line_width_min_pixels=1,
                pickable=True,
                auto_highlight=True,
            )
        )
    if show_school_1km:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                load_school_buffers(1),
                stroked=True,
                filled=True,
                get_fill_color=[247, 201, 72, 32],
                get_line_color=[176, 132, 0, 170],
                line_width_min_pixels=2,
                pickable=True,
                auto_highlight=True,
            )
        )
    if show_buildings:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                load_hdb_buildings(),
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
            data=points,
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
            "Hover a unit to see actual resale price when available, otherwise predicted price."
        )
        render_map(
            filtered,
            filters["metric"],
            filters["show_school_1km"],
            filters["show_school_2km"],
            filters["show_buildings"],
        )

    with chat_tab:
        render_api_status()
        st.divider()
        render_chatbot(filtered)


if __name__ == "__main__":
    main()
