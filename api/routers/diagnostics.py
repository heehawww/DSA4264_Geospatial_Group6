from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import TabularResponse

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/sign-trace", response_model=TabularResponse, summary="Trace of good-school coefficient sign changes")
def get_sign_trace(store: DataStore = Depends(get_store)) -> TabularResponse:
    df = store.sign_trace.copy().replace({np.nan: None})
    return {
        "count": int(len(df)),
        "filters": {},
        "rows": df.to_dict(orient="records"),
    }
