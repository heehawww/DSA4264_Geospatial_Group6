from __future__ import annotations

from fastapi import FastAPI

from .routers.benchmarks import router as benchmarks_router
from .routers.diagnostics import router as diagnostics_router
from .routers.model import router as model_router
from .routers.predict import router as predict_router
from .routers.rdd import router as rdd_router
from .routers.resales import router as resales_router
from .routers.system import router as system_router
from .routers.town_premiums import router as town_premiums_router

app = FastAPI(
    title="HDB School Premium API",
    version="0.1.0",
    description=(
        "FastAPI service exposing finalized HDB resale data, hedonic model outputs, "
        "school-specific RDD outputs, town premium estimates, diagnostics, benchmarks, and ridge predictions."
    ),
)

app.include_router(system_router)
app.include_router(model_router)
app.include_router(resales_router)
app.include_router(rdd_router)
app.include_router(town_premiums_router)
app.include_router(diagnostics_router)
app.include_router(benchmarks_router)
app.include_router(predict_router)
