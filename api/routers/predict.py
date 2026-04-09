from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from ..data import DataStore, NUMERIC_FEATURES, PREDICTIVE_CATEGORICAL_FEATURES
from ..dependencies import get_store
from ..schemas import PredictResponse, PredictSchemaResponse, PredictionRequest

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("/schema", response_model=PredictSchemaResponse, summary="Prediction input schema")
def get_prediction_schema(store: DataStore = Depends(get_store)) -> PredictSchemaResponse:
    return {
        "raw_request_fields": PredictionRequest.model_json_schema().get("properties", {}),
        "engineered_model_fields": NUMERIC_FEATURES + PREDICTIVE_CATEGORICAL_FEATURES,
        "defaults_used_when_omitted": store.defaults,
        "allowed_categories_sample": {
            key: values[:25]
            for key, values in store.allowed_categories.items()
        },
        "notes": [
            "Clients can send partial inputs; omitted fields are filled from dataset medians or modes.",
            "good_school_within_1km is derived from good_school_count_1km > 0 during prediction.",
            "For best results, send the raw distance and count fields, not the engineered log features.",
        ],
    }


@router.post("", response_model=PredictResponse, summary="Predict resale price with ridge model")
def predict_price(
    request: PredictionRequest,
    store: DataStore = Depends(get_store),
) -> PredictResponse:
    provided_fields = sorted(request.model_dump(exclude_none=True).keys())
    try:
        engineered, defaulted_fields = store.build_prediction_features(request.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    feature_frame = pd.DataFrame([engineered])[NUMERIC_FEATURES + PREDICTIVE_CATEGORICAL_FEATURES]
    predicted_log_price = float(store.ridge_pipeline.predict(feature_frame)[0])
    predicted_price = float(np.exp(predicted_log_price))
    used_defaults = len(defaulted_fields) > 0

    warning = None
    if used_defaults:
        if provided_fields:
            warning = (
                f"Only {len(provided_fields)} raw field(s) were provided; "
                f"{len(defaulted_fields)} field(s) were defaulted from the dataset profile."
            )
        else:
            warning = "No raw inputs were provided; all prediction inputs were defaulted from the dataset profile."

    return {
        "predicted_price": round(predicted_price, 2),
        "currency": "SGD",
        "used_defaults": used_defaults,
        "provided_raw_fields": provided_fields,
        "defaulted_raw_fields": defaulted_fields,
        "warning": warning,
        "engineered_features_used": engineered,
        "model": "ridge_pipeline.pkl",
        "note": "Prediction is based on the saved ridge hedonic model and is not a causal estimate.",
    }
