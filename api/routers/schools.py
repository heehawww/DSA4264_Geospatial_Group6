from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..data import DataStore
from ..dependencies import get_store
from ..schemas import GoodSchoolsResponse

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("/good", response_model=GoodSchoolsResponse, summary="Good primary schools linked to a town")
def get_good_schools(
    town: str | None = Query(default=None, description="Exact town name, for example HOUGANG"),
    limit: int = Query(default=50, ge=1, le=200),
    store: DataStore = Depends(get_store),
) -> GoodSchoolsResponse:
    rows = store.get_good_schools(town=town, limit=limit)
    return {
        "town": town,
        "count": len(rows),
        "rows": rows,
        "notes": [
            "These schools are derived by linking addresses in the resale feature dataset to good-school 1km boundary coverage.",
            "A school appears for a town when at least one address in that town falls within the good school's 1km area.",
        ],
    }
