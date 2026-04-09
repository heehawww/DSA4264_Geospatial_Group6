from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import TabularResponse

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("/summary", response_model=dict[str, Any], summary="Benchmark summary")
def get_benchmark_summary(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    df = store.benchmark_results.copy()
    best_r2_row = df.loc[pd.to_numeric(df["test_r2_log"], errors="coerce").idxmax()]
    best_rmse_row = df.loc[pd.to_numeric(df["test_rmse_sgd"], errors="coerce").idxmin()]
    return {
        "variant_count": int(len(df)),
        "best_by_test_r2_log": best_r2_row.replace({np.nan: None}).to_dict(),
        "best_by_test_rmse_sgd": best_rmse_row.replace({np.nan: None}).to_dict(),
        "metadata": store.benchmark_metadata,
    }


@router.get("/results", response_model=TabularResponse, summary="Benchmark comparison table")
def get_benchmark_results(
    variant: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.benchmark_results.copy()
    if variant:
        df = df.loc[df["variant"].astype(str).str.contains(variant, case=False, na=False)]
    df = df.head(limit).replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {"variant": variant, "limit": limit},
        "rows": df.to_dict(orient="records"),
    }


@router.get("/best", response_model=dict[str, Any], summary="Best benchmark variants")
def get_best_benchmarks(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    df = store.benchmark_results.copy()
    best_r2_row = df.loc[pd.to_numeric(df["test_r2_log"], errors="coerce").idxmax()]
    best_rmse_row = df.loc[pd.to_numeric(df["test_rmse_sgd"], errors="coerce").idxmin()]
    best_mae_row = df.loc[pd.to_numeric(df["test_mae_sgd"], errors="coerce").idxmin()]
    return {
        "best_by_test_r2_log": best_r2_row.replace({np.nan: None}).to_dict(),
        "best_by_test_rmse_sgd": best_rmse_row.replace({np.nan: None}).to_dict(),
        "best_by_test_mae_sgd": best_mae_row.replace({np.nan: None}).to_dict(),
    }


@router.get("/metadata", response_model=dict[str, Any], summary="Benchmark run metadata")
def get_benchmark_metadata(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    return store.benchmark_metadata
