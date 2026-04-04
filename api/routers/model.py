from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..data import DataStore
from ..dependencies import get_store

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/metrics", response_model=dict[str, Any], summary="Model metrics")
def get_model_metrics(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    return store.metrics
