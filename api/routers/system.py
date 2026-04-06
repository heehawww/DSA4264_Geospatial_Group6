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
            "GET /model/metrics",
            "GET /model/feature-importance",
            "GET /model/coefficients",
            "GET /model/coefficients/{term_name}",
            "GET /resales/raw",
            "GET /resales/schema",
            "GET /resales/summary",
            "GET /rdd/summary",
            "GET /rdd/schools",
            "GET /rdd/results",
            "GET /rdd/results/{school_name}",
            "GET /rdd/coefficients",
            "GET /rdd/group-ttests",
            "GET /rdd/skipped",
            "GET /town-premiums/summary",
            "GET /town-premiums",
            "GET /town-premiums/skipped",
            "GET /town-premiums/{town_name}",
            "GET /diagnostics/sign-trace",
            "GET /benchmarks/summary",
            "GET /benchmarks/results",
            "GET /benchmarks/best",
            "GET /benchmarks/metadata",
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
