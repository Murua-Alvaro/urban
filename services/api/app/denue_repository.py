from __future__ import annotations

from typing import Any

from sqlalchemy import text

from .db import engine


def list_editions() -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT
            source_edition,
            edition_date,
            is_rebenchmark,
            archive_sha256,
            metadata
        FROM denue_editions
        ORDER BY edition_date
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]


def municipality_timeseries(municipality_code: str) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT
            source_edition,
            edition_date,
            is_rebenchmark,
            establishments,
            active_agebs,
            active_grids
        FROM denue_municipality_totals
        WHERE municipality_code = :municipality_code
        ORDER BY edition_date
        """
    )
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(sql, {"municipality_code": municipality_code}).mappings()
        ]


def municipality_sector_summary(
    municipality_code: str,
    source_edition: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    sql = text(
        """
        WITH municipal AS (
            SELECT sector, SUM(establishments)::double precision AS establishments
            FROM denue_observations
            WHERE municipality_code = :municipality_code
              AND source_edition = :source_edition
            GROUP BY sector
        ),
        municipal_total AS (
            SELECT SUM(establishments) AS establishments FROM municipal
        ),
        state_sector AS (
            SELECT sector, SUM(establishments)::double precision AS establishments
            FROM denue_observations
            WHERE source_edition = :source_edition
            GROUP BY sector
        ),
        state_total AS (
            SELECT SUM(establishments) AS establishments FROM state_sector
        )
        SELECT
            m.sector,
            m.establishments::bigint AS establishments,
            m.establishments / NULLIF(mt.establishments, 0) AS municipality_share,
            s.establishments / NULLIF(st.establishments, 0) AS state_share,
            (m.establishments / NULLIF(mt.establishments, 0))
              / NULLIF(s.establishments / NULLIF(st.establishments, 0), 0) AS lq_state
        FROM municipal m
        CROSS JOIN municipal_total mt
        JOIN state_sector s USING (sector)
        CROSS JOIN state_total st
        ORDER BY m.establishments DESC, m.sector
        LIMIT :limit
        """
    )
    params = {
        "municipality_code": municipality_code,
        "source_edition": source_edition,
        "limit": limit,
    }
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).mappings()]


def municipality_grids(
    municipality_code: str,
    source_edition: str,
    min_establishments: int = 0,
) -> dict[str, Any]:
    sql = text(
        """
        WITH agg AS (
            SELECT
                grid_id,
                SUM(establishments)::bigint AS establishments,
                COUNT(DISTINCT sector)::integer AS sector_count,
                COUNT(DISTINCT scian6)::integer AS scian6_count,
                SUM(establishments) FILTER (WHERE has_phone)::double precision
                    / NULLIF(SUM(establishments), 0) AS phone_share,
                SUM(establishments) FILTER (WHERE has_email)::double precision
                    / NULLIF(SUM(establishments), 0) AS email_share,
                SUM(establishments) FILTER (WHERE has_web)::double precision
                    / NULLIF(SUM(establishments), 0) AS web_share
            FROM denue_observations
            WHERE municipality_code = :municipality_code
              AND source_edition = :source_edition
              AND NOT missing_grid
            GROUP BY grid_id
        )
        SELECT
            a.grid_id,
            a.establishments,
            a.sector_count,
            a.scian6_count,
            a.phone_share,
            a.email_share,
            a.web_share,
            ST_AsGeoJSON(g.geom)::json AS geometry
        FROM agg a
        LEFT JOIN denue_grid_geometries g
          ON g.municipality_code = :municipality_code
         AND g.grid_id = a.grid_id
        WHERE a.establishments >= :min_establishments
        ORDER BY a.establishments DESC, a.grid_id
        """
    )
    params = {
        "municipality_code": municipality_code,
        "source_edition": source_edition,
        "min_establishments": min_establishments,
    }
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, params).mappings()]

    features = []
    for row in rows:
        geometry = row.pop("geometry")
        features.append(
            {
                "type": "Feature",
                "id": f"{municipality_code}|{row['grid_id']}",
                "geometry": geometry,
                "properties": row,
            }
        )
    return {
        "type": "FeatureCollection",
        "municipality_code": municipality_code,
        "source_edition": source_edition,
        "features": features,
    }


def quality_by_edition() -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT
            o.source_edition,
            e.edition_date,
            SUM(o.establishments)::bigint AS establishments,
            SUM(o.establishments) FILTER (WHERE o.missing_ageb)::double precision
                / NULLIF(SUM(o.establishments), 0) AS missing_ageb_share,
            SUM(o.establishments) FILTER (WHERE o.missing_grid)::double precision
                / NULLIF(SUM(o.establishments), 0) AS missing_grid_share,
            SUM(o.establishments) FILTER (WHERE o.missing_postal_code)::double precision
                / NULLIF(SUM(o.establishments), 0) AS missing_postal_share
        FROM denue_observations o
        JOIN denue_editions e USING (source_edition)
        GROUP BY o.source_edition, e.edition_date
        ORDER BY e.edition_date
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]
