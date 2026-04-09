from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import TabularResponse

router = APIRouter(prefix="/town-premiums", tags=["town-premiums"])


@router.get("/summary", response_model=dict[str, Any], summary="Town premium summary statistics")
def get_town_premium_summary(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    df = store.town_premium_results.copy()
    premium_pct = pd.to_numeric(df["premium_pct_per_additional_good_school_1km"], errors="coerce")
    premium_sgd = pd.to_numeric(df["premium_sgd_per_additional_good_school_1km_at_town_mean_price"], errors="coerce")
    return {
        "count": int(len(df)),
        "mean_premium_pct": float(premium_pct.mean()) if not premium_pct.empty else None,
        "median_premium_pct": float(premium_pct.median()) if not premium_pct.empty else None,
        "mean_premium_sgd_at_town_mean_price": float(premium_sgd.mean()) if not premium_sgd.empty else None,
        "median_premium_sgd_at_town_mean_price": float(premium_sgd.median()) if not premium_sgd.empty else None,
        "skipped_town_count": int(len(store.town_premium_skipped)),
    }


@router.get("", response_model=TabularResponse, summary="Town premium results")
def get_town_premiums(
    town: str | None = Query(default=None),
    min_p_value: float | None = Query(default=None),
    max_p_value: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.town_premium_results.copy()
    if town:
        df = df.loc[df["town"].astype(str).str.contains(town, case=False, na=False)]
    p_values = pd.to_numeric(df["p_value"], errors="coerce")
    if min_p_value is not None:
        df = df.loc[p_values >= min_p_value]
        p_values = pd.to_numeric(df["p_value"], errors="coerce")
    if max_p_value is not None:
        df = df.loc[p_values <= max_p_value]
    df = df.head(limit).replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "town": town,
            "min_p_value": min_p_value,
            "max_p_value": max_p_value,
            "limit": limit,
        },
        "rows": df.to_dict(orient="records"),
    }


@router.get("/skipped", response_model=TabularResponse, summary="Skipped towns for town premium models")
def get_town_premium_skipped(store: DataStore = Depends(get_store)) -> TabularResponse:
    df = store.town_premium_skipped.copy().replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {},
        "rows": df.to_dict(orient="records"),
    }


@router.get("/{town_name}", response_model=dict[str, Any], summary="Town premium result for one town")
def get_town_premium(
    town_name: str,
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    df = store.town_premium_results.copy()
    row = df.loc[df["town"].astype(str).str.lower() == town_name.lower()]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"No town premium result found for '{town_name}'")
    return {"row": row.iloc[0].replace({np.nan: None}).to_dict()}
