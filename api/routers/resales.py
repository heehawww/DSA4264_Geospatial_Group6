from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import RawResalesResponse, ResalesSchemaResponse, ResalesSummaryResponse

router = APIRouter(prefix="/resales", tags=["resales"])

SUPPORTED_GROUP_BY = [
    "town",
    "flat_type",
    "flat_model",
    "month",
    "storey_range",
]


def _get_resales_dataframe(store: DataStore) -> tuple[pd.DataFrame, str, str]:
    if store.raw_dataset is not None:
        return store.raw_dataset.copy(), "raw_input", str(store.raw_dataset_path)
    return store.feature_dataset.copy(), "processed_feature_table_fallback", str(store.feature_dataset_path)


def _apply_common_resale_filters(
    df: pd.DataFrame,
    *,
    town: list[str] | None = None,
    flat_type: list[str] | None = None,
    flat_model: list[str] | None = None,
    street_name: list[str] | None = None,
    block: list[str] | None = None,
    storey_range: list[str] | None = None,
    month: list[str] | None = None,
    month_from: str | None = None,
    month_to: str | None = None,
    min_floor_area_sqm: float | None = None,
    max_floor_area_sqm: float | None = None,
    min_lease_commence_date: int | None = None,
    max_lease_commence_date: int | None = None,
    min_resale_price: float | None = None,
    max_resale_price: float | None = None,
    min_school_count_1km: float | None = None,
    max_school_count_1km: float | None = None,
    min_good_school_count_1km: float | None = None,
    max_good_school_count_1km: float | None = None,
    min_school_count_2km: float | None = None,
    max_school_count_2km: float | None = None,
    min_good_school_count_2km: float | None = None,
    max_good_school_count_2km: float | None = None,
) -> pd.DataFrame:
    if town and "town" in df.columns:
        wanted = {value.upper() for value in town}
        df = df.loc[df["town"].astype(str).str.upper().isin(wanted)]
    if flat_type and "flat_type" in df.columns:
        wanted = {value.upper() for value in flat_type}
        df = df.loc[df["flat_type"].astype(str).str.upper().isin(wanted)]
    if flat_model and "flat_model" in df.columns:
        wanted = {value.upper() for value in flat_model}
        df = df.loc[df["flat_model"].astype(str).str.upper().isin(wanted)]
    if street_name and "street_name" in df.columns:
        wanted = {value.upper() for value in street_name}
        df = df.loc[df["street_name"].astype(str).str.upper().isin(wanted)]
    if block and "block" in df.columns:
        wanted = {value.upper() for value in block}
        df = df.loc[df["block"].astype(str).str.upper().isin(wanted)]
    if storey_range and "storey_range" in df.columns:
        wanted = {value.upper() for value in storey_range}
        df = df.loc[df["storey_range"].astype(str).str.upper().isin(wanted)]
    if month and "month" in df.columns:
        wanted = set(month)
        df = df.loc[df["month"].astype(str).isin(wanted)]
    if month_from and "month" in df.columns:
        df = df.loc[df["month"].astype(str) >= month_from]
    if month_to and "month" in df.columns:
        df = df.loc[df["month"].astype(str) <= month_to]

    numeric_ranges = [
        ("floor_area_sqm", min_floor_area_sqm, max_floor_area_sqm),
        ("lease_commence_date", min_lease_commence_date, max_lease_commence_date),
        ("resale_price", min_resale_price, max_resale_price),
        ("school_count_1km", min_school_count_1km, max_school_count_1km),
        ("good_school_count_1km", min_good_school_count_1km, max_good_school_count_1km),
        ("school_count_2km", min_school_count_2km, max_school_count_2km),
        ("good_school_count_2km", min_good_school_count_2km, max_good_school_count_2km),
    ]
    for column, minimum, maximum in numeric_ranges:
        if column not in df.columns:
            continue
        series = pd.to_numeric(df[column], errors="coerce")
        if minimum is not None:
            df = df.loc[series >= minimum]
            series = pd.to_numeric(df[column], errors="coerce")
        if maximum is not None:
            df = df.loc[series <= maximum]

    return df


@router.get("/schema", response_model=ResalesSchemaResponse, summary="Resale filter and grouping schema")
def get_resales_schema(store: DataStore = Depends(get_store)) -> ResalesSchemaResponse:
    df, dataset_kind, dataset_path = _get_resales_dataframe(store)
    return {
        "dataset_kind": dataset_kind,
        "dataset_path": dataset_path,
        "is_true_raw_dataset": store.raw_dataset is not None,
        "available_columns": df.columns.tolist(),
        "supported_filters": {
            "categorical_multi": [
                "town",
                "flat_type",
                "flat_model",
                "street_name",
                "block",
                "storey_range",
                "month",
            ],
            "range_filters": [
                "month_from",
                "month_to",
                "min_floor_area_sqm",
                "max_floor_area_sqm",
                "min_lease_commence_date",
                "max_lease_commence_date",
                "min_resale_price",
                "max_resale_price",
                "min_school_count_1km",
                "max_school_count_1km",
                "min_good_school_count_1km",
                "max_good_school_count_1km",
                "min_school_count_2km",
                "max_school_count_2km",
                "min_good_school_count_2km",
                "max_good_school_count_2km",
            ],
        },
        "supported_group_by": SUPPORTED_GROUP_BY,
        "notes": [
            "This endpoint exposes a curated filter surface rather than arbitrary column filtering.",
            "If the true raw resale CSV is missing, the schema reflects the processed feature-table fallback.",
            "Use /resales/raw for row-level retrieval and /resales/summary for aggregated statistics.",
        ],
    }


@router.get("/raw", response_model=RawResalesResponse, summary="Row-level resale data")
def get_raw_resales(
    town: list[str] | None = Query(default=None),
    flat_type: list[str] | None = Query(default=None),
    flat_model: list[str] | None = Query(default=None),
    street_name: list[str] | None = Query(default=None),
    block: list[str] | None = Query(default=None),
    storey_range: list[str] | None = Query(default=None),
    month: list[str] | None = Query(default=None),
    month_from: str | None = Query(default=None),
    month_to: str | None = Query(default=None),
    min_floor_area_sqm: float | None = Query(default=None),
    max_floor_area_sqm: float | None = Query(default=None),
    min_lease_commence_date: int | None = Query(default=None),
    max_lease_commence_date: int | None = Query(default=None),
    min_resale_price: float | None = Query(default=None),
    max_resale_price: float | None = Query(default=None),
    min_school_count_1km: float | None = Query(default=None),
    max_school_count_1km: float | None = Query(default=None),
    min_good_school_count_1km: float | None = Query(default=None),
    max_good_school_count_1km: float | None = Query(default=None),
    min_school_count_2km: float | None = Query(default=None),
    max_school_count_2km: float | None = Query(default=None),
    min_good_school_count_2km: float | None = Query(default=None),
    max_good_school_count_2km: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: DataStore = Depends(get_store),
) -> RawResalesResponse:
    df, dataset_kind, dataset_path = _get_resales_dataframe(store)
    df = _apply_common_resale_filters(
        df,
        town=town,
        flat_type=flat_type,
        flat_model=flat_model,
        street_name=street_name,
        block=block,
        storey_range=storey_range,
        month=month,
        month_from=month_from,
        month_to=month_to,
        min_floor_area_sqm=min_floor_area_sqm,
        max_floor_area_sqm=max_floor_area_sqm,
        min_lease_commence_date=min_lease_commence_date,
        max_lease_commence_date=max_lease_commence_date,
        min_resale_price=min_resale_price,
        max_resale_price=max_resale_price,
        min_school_count_1km=min_school_count_1km,
        max_school_count_1km=max_school_count_1km,
        min_good_school_count_1km=min_good_school_count_1km,
        max_good_school_count_1km=max_good_school_count_1km,
        min_school_count_2km=min_school_count_2km,
        max_school_count_2km=max_school_count_2km,
        min_good_school_count_2km=min_good_school_count_2km,
        max_good_school_count_2km=max_good_school_count_2km,
    )

    df = df.head(limit).replace({np.nan: None})
    return {
        "dataset_kind": dataset_kind,
        "dataset_path": dataset_path,
        "is_true_raw_dataset": store.raw_dataset is not None,
        "note": (
            "No CSV was found in data/resale_hdbs_raw.csv or data/resale_flat_prices.csv, so this endpoint is currently serving the processed feature dataset."
            if store.raw_dataset is None
            else f"Serving the uploaded raw resale dataset from {dataset_path}."
        ),
        "count": int(len(df)),
        "rows": df.to_dict(orient="records"),
    }


@router.get("/summary", response_model=ResalesSummaryResponse, summary="Aggregated resale statistics")
def get_resales_summary(
    town: list[str] | None = Query(default=None),
    flat_type: list[str] | None = Query(default=None),
    flat_model: list[str] | None = Query(default=None),
    street_name: list[str] | None = Query(default=None),
    block: list[str] | None = Query(default=None),
    storey_range: list[str] | None = Query(default=None),
    month_from: str | None = Query(default=None),
    month_to: str | None = Query(default=None),
    min_floor_area_sqm: float | None = Query(default=None),
    max_floor_area_sqm: float | None = Query(default=None),
    min_lease_commence_date: int | None = Query(default=None),
    max_lease_commence_date: int | None = Query(default=None),
    min_resale_price: float | None = Query(default=None),
    max_resale_price: float | None = Query(default=None),
    min_school_count_1km: float | None = Query(default=None),
    max_school_count_1km: float | None = Query(default=None),
    min_good_school_count_1km: float | None = Query(default=None),
    max_good_school_count_1km: float | None = Query(default=None),
    min_school_count_2km: float | None = Query(default=None),
    max_school_count_2km: float | None = Query(default=None),
    min_good_school_count_2km: float | None = Query(default=None),
    max_good_school_count_2km: float | None = Query(default=None),
    group_by: str | None = Query(default=None, description="town, flat_type, flat_model, month, or storey_range"),
    store: DataStore = Depends(get_store),
) -> ResalesSummaryResponse:
    df, dataset_kind, dataset_path = _get_resales_dataframe(store)
    df = _apply_common_resale_filters(
        df,
        town=town,
        flat_type=flat_type,
        flat_model=flat_model,
        street_name=street_name,
        block=block,
        storey_range=storey_range,
        month_from=month_from,
        month_to=month_to,
        min_floor_area_sqm=min_floor_area_sqm,
        max_floor_area_sqm=max_floor_area_sqm,
        min_lease_commence_date=min_lease_commence_date,
        max_lease_commence_date=max_lease_commence_date,
        min_resale_price=min_resale_price,
        max_resale_price=max_resale_price,
        min_school_count_1km=min_school_count_1km,
        max_school_count_1km=max_school_count_1km,
        min_good_school_count_1km=min_good_school_count_1km,
        max_good_school_count_1km=max_good_school_count_1km,
        min_school_count_2km=min_school_count_2km,
        max_school_count_2km=max_school_count_2km,
        min_good_school_count_2km=min_good_school_count_2km,
        max_good_school_count_2km=max_good_school_count_2km,
    )

    if "resale_price" not in df.columns:
        raise HTTPException(status_code=422, detail="Dataset does not contain resale_price")

    prices = pd.to_numeric(df["resale_price"], errors="coerce").dropna()
    summary = {
        "count": int(len(prices)),
        "mean_resale_price": float(prices.mean()) if not prices.empty else None,
        "median_resale_price": float(prices.median()) if not prices.empty else None,
        "min_resale_price": float(prices.min()) if not prices.empty else None,
        "max_resale_price": float(prices.max()) if not prices.empty else None,
    }

    grouped_rows: list[dict[str, Any]] = []
    if group_by:
        if group_by not in SUPPORTED_GROUP_BY:
            raise HTTPException(status_code=422, detail=f"group_by must be one of {SUPPORTED_GROUP_BY}")
        if group_by not in df.columns:
            raise HTTPException(status_code=422, detail=f"Dataset does not contain {group_by}")

        grouped = (
            df.assign(resale_price_num=pd.to_numeric(df["resale_price"], errors="coerce"))
            .dropna(subset=["resale_price_num"])
            .groupby(group_by, dropna=False)["resale_price_num"]
            .agg(["count", "mean", "median", "min", "max"])
            .reset_index()
        )
        grouped = grouped.replace({np.nan: None})
        grouped_rows = grouped.rename(
            columns={
                "mean": "mean_resale_price",
                "median": "median_resale_price",
                "min": "min_resale_price",
                "max": "max_resale_price",
            }
        ).to_dict(orient="records")

    return {
        "dataset_kind": dataset_kind,
        "dataset_path": dataset_path,
        "is_true_raw_dataset": store.raw_dataset is not None,
        "note": (
            "No CSV was found in data/resale_hdbs_raw.csv or data/resale_flat_prices.csv, so summaries are currently based on the processed feature dataset."
            if store.raw_dataset is None
            else f"Summaries are based on the uploaded raw resale dataset at {dataset_path}."
        ),
        "filters": {
            "town": town,
            "flat_type": flat_type,
            "flat_model": flat_model,
            "street_name": street_name,
            "block": block,
            "storey_range": storey_range,
            "month_from": month_from,
            "month_to": month_to,
            "min_floor_area_sqm": min_floor_area_sqm,
            "max_floor_area_sqm": max_floor_area_sqm,
            "min_lease_commence_date": min_lease_commence_date,
            "max_lease_commence_date": max_lease_commence_date,
            "min_resale_price": min_resale_price,
            "max_resale_price": max_resale_price,
            "min_school_count_1km": min_school_count_1km,
            "max_school_count_1km": max_school_count_1km,
            "min_good_school_count_1km": min_good_school_count_1km,
            "max_good_school_count_1km": max_good_school_count_1km,
            "min_school_count_2km": min_school_count_2km,
            "max_school_count_2km": max_school_count_2km,
            "min_good_school_count_2km": min_good_school_count_2km,
            "max_good_school_count_2km": max_good_school_count_2km,
            "group_by": group_by,
        },
        "summary": summary,
        "grouped_rows": grouped_rows,
    }
