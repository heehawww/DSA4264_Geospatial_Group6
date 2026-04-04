from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import PremiumListResponse

router = APIRouter(prefix="/premiums", tags=["premiums"])


@router.get("/summary", response_model=dict[str, object], summary="Premium dataset summary")
def get_premium_summary(store: DataStore = Depends(get_store)) -> dict[str, object]:
    return store.premium_summary


@router.get("", response_model=PremiumListResponse, summary="Scored premium rows")
def get_premiums(
    town: list[str] | None = Query(default=None),
    flat_type: list[str] | None = Query(default=None),
    min_premium_sgd: float | None = Query(default=None),
    max_premium_sgd: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: DataStore = Depends(get_store),
) -> PremiumListResponse:
    df = store.premium_rows.copy()
    if town:
        wanted = {value.upper() for value in town}
        df = df.loc[df["town"].astype(str).str.upper().isin(wanted)]
    if flat_type:
        wanted = {value.upper() for value in flat_type}
        df = df.loc[df["flat_type"].astype(str).str.upper().isin(wanted)]
    if min_premium_sgd is not None:
        df = df.loc[pd.to_numeric(df["estimated_good_school_1km_premium_sgd"], errors="coerce") >= min_premium_sgd]
    if max_premium_sgd is not None:
        df = df.loc[pd.to_numeric(df["estimated_good_school_1km_premium_sgd"], errors="coerce") <= max_premium_sgd]

    summary = {
        "matched_rows": int(len(df)),
        "mean_premium_sgd": float(pd.to_numeric(df["estimated_good_school_1km_premium_sgd"], errors="coerce").mean()) if not df.empty else None,
        "median_premium_sgd": float(pd.to_numeric(df["estimated_good_school_1km_premium_sgd"], errors="coerce").median()) if not df.empty else None,
    }

    df = df.head(limit).where(pd.notnull(df), None)
    return {
        "summary": summary,
        "filters": {
            "town": town,
            "flat_type": flat_type,
            "min_premium_sgd": min_premium_sgd,
            "max_premium_sgd": max_premium_sgd,
            "limit": limit,
        },
        "rows": df.to_dict(orient="records"),
    }
