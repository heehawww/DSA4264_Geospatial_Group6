from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import TabularResponse

router = APIRouter(prefix="/ols", tags=["ols"])


@router.get("/coefficients", response_model=TabularResponse, summary="Search OLS coefficients")
def get_ols_coefficients(
    term: str | None = Query(default=None, description="Case-insensitive term search"),
    significant_only: bool = Query(default=False, description="Keep only p_value < 0.05"),
    limit: int = Query(default=100, ge=1, le=1000),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.ols_coefficients.copy()
    if term:
        mask = df["term"].astype(str).str.contains(term, case=False, na=False)
        df = df.loc[mask]
    if significant_only and "p_value" in df.columns:
        df = df.loc[pd.to_numeric(df["p_value"], errors="coerce") < 0.05]

    df = df.head(limit).replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "term": term,
            "significant_only": significant_only,
            "limit": limit,
        },
        "rows": df.to_dict(orient="records"),
    }


@router.get("/coefficients/{term_name}", response_model=dict[str, Any], summary="Get one OLS coefficient")
def get_ols_coefficient(
    term_name: str,
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    df = store.ols_coefficients.copy()
    row = df.loc[df["term"].astype(str).str.lower() == term_name.lower()]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Coefficient term '{term_name}' not found")
    result = row.iloc[0].replace({np.nan: None}).to_dict()
    return {"row": result}
