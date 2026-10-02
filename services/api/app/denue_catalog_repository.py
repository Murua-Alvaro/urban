from __future__ import annotations

from typing import Any

from sqlalchemy import text

from .db import engine


def list_municipalities() -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT
            geokey AS municipality_code,
            name,
            ST_Y(centroid) AS latitude,
            ST_X(centroid) AS longitude,
            metadata -> 'years' AS editions
        FROM geographies
        WHERE geography_type = 'municipality'
          AND parent_geokey = '25'
        ORDER BY name
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]
