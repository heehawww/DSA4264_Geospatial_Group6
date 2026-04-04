from __future__ import annotations

from fastapi import FastAPI

from .routers.model import router as model_router
from .routers.ols import router as ols_router
from .routers.predict import router as predict_router
from .routers.premiums import router as premiums_router
from .routers.rdd import router as rdd_router
from .routers.resales import router as resales_router
from .routers.system import router as system_router

app = FastAPI(
    title="HDB School Premium API",
    version="0.1.0",
    description=(
        "FastAPI service exposing OLS coefficients, aggregated RDD outputs, "
        "transaction-level school premium estimates, raw/feature datasets, and ridge predictions."
    ),
)

app.include_router(system_router)
app.include_router(ols_router)
app.include_router(model_router)
app.include_router(rdd_router)
app.include_router(premiums_router)
app.include_router(resales_router)
app.include_router(predict_router)
