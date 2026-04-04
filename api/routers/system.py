from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import HealthResponse, MetadataResponse

router = APIRouter(tags=["system"])


@router.get("/", response_model=dict[str, Any], summary="List available endpoints")
def root() -> dict[str, Any]:
    return {
        "name": "HDB School Premium API",
        "version": "0.1.0",
        "endpoints": [
            "GET /health",
            "GET /metadata",
            "GET /ols/coefficients",
            "GET /ols/coefficients/{term_name}",
            "GET /model/metrics",
            "GET /rdd/summary",
            "GET /rdd/results",
            "GET /premiums/summary",
            "GET /premiums",
            "GET /resales/raw",
            "GET /resales/summary",
            "GET /predict/schema",
            "POST /predict",
        ],
    }


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health() -> HealthResponse:
    return {"status": "ok"}


@router.get("/metadata", response_model=MetadataResponse, summary="Dataset and model metadata")
def metadata(store: DataStore = Depends(get_store)) -> MetadataResponse:
    return store.dataset_metadata()
