from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import TabularResponse

router = APIRouter(prefix="/rdd", tags=["rdd"])


@router.get("/summary", response_model=dict[str, Any], summary="RDD metadata summary")
def get_rdd_summary(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    return store.rdd_summary


@router.get("/schools", response_model=TabularResponse, summary="School coverage across RDD outputs")
def get_rdd_schools(store: DataStore = Depends(get_store)) -> TabularResponse:
    results = (
        store.rdd_results.groupby(["boundary_school_name", "school_group"], dropna=False)
        .size()
        .reset_index(name="result_rows")
    )
    skipped = (
        store.rdd_skipped.groupby(["boundary_school_name", "school_group"], dropna=False)
        .size()
        .reset_index(name="skipped_rows")
    )
    merged = results.merge(
        skipped,
        on=["boundary_school_name", "school_group"],
        how="outer",
    ).fillna(0)
    merged["result_rows"] = merged["result_rows"].astype(int)
    merged["skipped_rows"] = merged["skipped_rows"].astype(int)
    merged["has_results"] = merged["result_rows"] > 0
    merged = merged.sort_values(["school_group", "boundary_school_name"])
    return {
        "count": int(len(merged)),
        "filters": {},
        "rows": merged.to_dict(orient="records"),
    }


@router.get("/results", response_model=TabularResponse, summary="School-specific RDD main results")
def get_rdd_results(
    school_name: str | None = Query(default=None),
    school_group: str | None = Query(default=None),
    specification: str | None = Query(default=None),
    bandwidth_m: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.rdd_results.copy()
    if school_name:
        df = df.loc[df["boundary_school_name"].astype(str).str.contains(school_name, case=False, na=False)]
    if school_group:
        df = df.loc[df["school_group"].astype(str).str.lower() == school_group.lower()]
    if specification:
        df = df.loc[df["specification"].astype(str).str.lower() == specification.lower()]
    if bandwidth_m is not None:
        df = df.loc[pd.to_numeric(df["bandwidth_m"], errors="coerce") == bandwidth_m]
    df = df.head(limit).replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "school_name": school_name,
            "school_group": school_group,
            "specification": specification,
            "bandwidth_m": bandwidth_m,
            "limit": limit,
        },
        "rows": df.to_dict(orient="records"),
    }


@router.get("/results/{school_name}", response_model=dict[str, Any], summary="RDD results for one school")
def get_rdd_results_for_school(
    school_name: str,
    specification: str | None = Query(default=None),
    bandwidth_m: int | None = Query(default=None),
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    df = store.rdd_results.copy()
    df = df.loc[df["boundary_school_name"].astype(str).str.lower() == school_name.lower()]
    if specification:
        df = df.loc[df["specification"].astype(str).str.lower() == specification.lower()]
    if bandwidth_m is not None:
        df = df.loc[pd.to_numeric(df["bandwidth_m"], errors="coerce") == bandwidth_m]
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No RDD results found for '{school_name}'")
    return {
        "school_name": school_name,
        "count": int(len(df)),
        "rows": df.replace({np.nan: None}).to_dict(orient="records"),
    }


@router.get("/coefficients", response_model=TabularResponse, summary="School-specific RDD coefficient tables")
def get_rdd_coefficients(
    school_name: str | None = Query(default=None),
    school_group: str | None = Query(default=None),
    specification: str | None = Query(default=None),
    bandwidth_m: int | None = Query(default=None),
    term: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.rdd_coefficients.copy()
    if school_name:
        df = df.loc[df["boundary_school_name"].astype(str).str.contains(school_name, case=False, na=False)]
    if school_group:
        df = df.loc[df["school_group"].astype(str).str.lower() == school_group.lower()]
    if specification:
        df = df.loc[df["specification"].astype(str).str.lower() == specification.lower()]
    if bandwidth_m is not None:
        df = df.loc[pd.to_numeric(df["bandwidth_m"], errors="coerce") == bandwidth_m]
    if term:
        df = df.loc[df["term"].astype(str).str.contains(term, case=False, na=False)]
    df = df.head(limit).replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "school_name": school_name,
            "school_group": school_group,
            "specification": specification,
            "bandwidth_m": bandwidth_m,
            "term": term,
            "limit": limit,
        },
        "rows": df.to_dict(orient="records"),
    }


@router.get("/group-comparison", response_model=TabularResponse, summary="Good vs non-good school interaction comparison")
def get_rdd_group_comparison(
    specification: str | None = Query(default=None),
    bandwidth_m: int | None = Query(default=None),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.rdd_group_comparison_results.copy()
    if specification:
        df = df.loc[df["specification"].astype(str).str.lower() == specification.lower()]
    if bandwidth_m is not None:
        df = df.loc[pd.to_numeric(df["bandwidth_m"], errors="coerce") == bandwidth_m]
    df = df.replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "specification": specification,
            "bandwidth_m": bandwidth_m,
        },
        "rows": df.to_dict(orient="records"),
    }


@router.get("/group-comparison/coefficients", response_model=TabularResponse, summary="Interaction-model coefficient table")
def get_rdd_group_comparison_coefficients(
    specification: str | None = Query(default=None),
    bandwidth_m: int | None = Query(default=None),
    term: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.rdd_group_comparison_coefficients.copy()
    if specification:
        df = df.loc[df["specification"].astype(str).str.lower() == specification.lower()]
    if bandwidth_m is not None:
        df = df.loc[pd.to_numeric(df["bandwidth_m"], errors="coerce") == bandwidth_m]
    if term:
        df = df.loc[df["term"].astype(str).str.contains(term, case=False, na=False)]
    df = df.head(limit).replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "specification": specification,
            "bandwidth_m": bandwidth_m,
            "term": term,
            "limit": limit,
        },
        "rows": df.to_dict(orient="records"),
    }


@router.get("/skipped", response_model=TabularResponse, summary="Schools excluded from RDD estimation")
def get_rdd_skipped(
    school_name: str | None = Query(default=None),
    school_group: str | None = Query(default=None),
    reason: str | None = Query(default=None),
    bandwidth_m: int | None = Query(default=None),
    store: DataStore = Depends(get_store),
) -> TabularResponse:
    df = store.rdd_skipped.copy()
    if school_name:
        df = df.loc[df["boundary_school_name"].astype(str).str.contains(school_name, case=False, na=False)]
    if school_group:
        df = df.loc[df["school_group"].astype(str).str.lower() == school_group.lower()]
    if reason:
        df = df.loc[df["reason"].astype(str).str.contains(reason, case=False, na=False)]
    if bandwidth_m is not None:
        df = df.loc[pd.to_numeric(df["bandwidth_m"], errors="coerce") == bandwidth_m]
    df = df.replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {
            "school_name": school_name,
            "school_group": school_group,
            "reason": reason,
            "bandwidth_m": bandwidth_m,
        },
        "rows": df.to_dict(orient="records"),
    }
