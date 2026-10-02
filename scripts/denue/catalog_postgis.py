from __future__ import annotations

import json
from pathlib import Path

import psycopg


def load_municipality_catalog(conn: psycopg.Connection, data_root: Path) -> int:
    """Persist the state and municipality catalog embedded in the audited archive."""
    core = json.loads((data_root / "core.json").read_text(encoding="utf-8"))
    municipalities = core["manifest"]["municipalities"]

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO geographies (geokey, geography_type, name, metadata)
                VALUES ('25', 'state', 'Sinaloa', '{"source":"DENUE historical archive"}'::jsonb)
                ON CONFLICT (geokey) DO UPDATE SET
                    geography_type = EXCLUDED.geography_type,
                    name = EXCLUDED.name,
                    metadata = geographies.metadata || EXCLUDED.metadata
                """
            )
            for code, item in municipalities.items():
                center = item.get("center") or [None, None]
                latitude = center[0]
                longitude = center[1]
                metadata = {
                    "state_code": item.get("state_code"),
                    "mun_code": item.get("mun_code"),
                    "geometry_url": item.get("geometry_url"),
                    "years": item.get("years", []),
                }
                cur.execute(
                    """
                    INSERT INTO geographies
                        (geokey, geography_type, name, parent_geokey, centroid, metadata)
                    VALUES (
                        %s, 'municipality', %s, '25',
                        CASE
                            WHEN %s IS NULL OR %s IS NULL THEN NULL
                            ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                        END,
                        %s::jsonb
                    )
                    ON CONFLICT (geokey) DO UPDATE SET
                        geography_type = EXCLUDED.geography_type,
                        name = EXCLUDED.name,
                        parent_geokey = EXCLUDED.parent_geokey,
                        centroid = EXCLUDED.centroid,
                        metadata = geographies.metadata || EXCLUDED.metadata
                    """,
                    (
                        code,
                        item.get("name"),
                        longitude,
                        latitude,
                        longitude,
                        latitude,
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
    return len(municipalities)
