from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError

from .denue_repository import (
    list_editions,
    municipality_grids,
    municipality_sector_summary,
    municipality_timeseries,
    quality_by_edition,
)

router = APIRouter(prefix="/v1/denue", tags=["DENUE"])
MUNICIPALITY_PATTERN = r"^25_\d{3}$"
EDITION_PATTERN = r"^\d{4}(?:-(?:A|B|\d{2}))?$"


def _db_unavailable(exc: SQLAlchemyError) -> HTTPException:
    return HTTPException(status_code=503, detail="DENUE analytical database is unavailable")


@router.get("/editions")
def editions() -> dict:
    try:
        rows = list_editions()
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc
    return {"count": len(rows), "editions": rows}


@router.get("/quality")
def quality() -> dict:
    try:
        rows = quality_by_edition()
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc
    return {"count": len(rows), "quality": rows}


@router.get("/municipalities/{municipality_code}/timeseries")
def timeseries(
    municipality_code: str = Path(pattern=MUNICIPALITY_PATTERN),
) -> dict:
    try:
        rows = municipality_timeseries(municipality_code)
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Municipality has no DENUE observations")
    return {"municipality_code": municipality_code, "count": len(rows), "observations": rows}


@router.get("/municipalities/{municipality_code}/sectors")
def sectors(
    municipality_code: str = Path(pattern=MUNICIPALITY_PATTERN),
    edition: str = Query(pattern=EDITION_PATTERN),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict:
    try:
        rows = municipality_sector_summary(municipality_code, edition, limit=limit)
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="No DENUE data for municipality/edition")
    return {
        "municipality_code": municipality_code,
        "source_edition": edition,
        "count": len(rows),
        "sectors": rows,
    }


@router.get("/municipalities/{municipality_code}/grids")
def grids(
    municipality_code: str = Path(pattern=MUNICIPALITY_PATTERN),
    edition: str = Query(pattern=EDITION_PATTERN),
    min_establishments: int = Query(default=0, ge=0),
) -> dict:
    try:
        collection = municipality_grids(
            municipality_code,
            edition,
            min_establishments=min_establishments,
        )
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc
    if not collection["features"]:
        raise HTTPException(status_code=404, detail="No DENUE grids for municipality/edition")
    return collection
