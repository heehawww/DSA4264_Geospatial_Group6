from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import TabularResponse

router = APIRouter(prefix="/rdd", tags=["rdd"])


@router.get("/summary", response_model=dict[str, Any], summary="RDD metadata summary")
def get_rdd_summary(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    return store.rdd_summary


@router.get("/results", response_model=TabularResponse, summary="Aggregated RDD results")
def get_rdd_results(
    specification: str | None = Query(default=None, description="controlled, school_fe, uncontrolled"),
    bandwidth_m: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.rdd_results.copy()
    if specification:
        df = df.loc[df["specification"].astype(str).str.lower() == specification.lower()]
    if bandwidth_m is not None:
        df = df.loc[pd.to_numeric(df["bandwidth_m"], errors="coerce") == bandwidth_m]

    df = df.head(limit).replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "specification": specification,
            "bandwidth_m": bandwidth_m,
            "limit": limit,
        },
        "rows": df.to_dict(orient="records"),
    }
