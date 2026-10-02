from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import psycopg

ARCHIVE_SHA256 = "182c22a2a96189e47d4e0d6b5dfd2a34a09307cfa3af57b1503664cdecc1bff3"
EXPECTED_FIELDS = ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"]
EDITION_DATES = {
    "2010": "2010-07-01", "2011": "2011-03-01", "2012": "2012-06-01",
    "2013-A": "2013-07-01", "2013-B": "2013-10-01", "2015-02": "2015-01-01",
    "2016-01": "2016-01-01", "2016-10": "2016-10-01", "2017-03": "2017-03-01",
    "2017-11": "2017-11-01", "2018-03": "2018-03-01", "2018-11": "2018-11-01",
    "2019-04": "2019-04-01", "2019-11": "2019-11-01", "2020-04": "2020-04-01",
    "2020-11": "2020-11-01", "2021-05": "2021-05-01", "2021-11": "2021-11-01",
    "2022-05": "2022-05-01", "2022-11": "2022-11-01", "2023-11": "2023-11-01",
    "2024-05": "2024-05-01", "2024-11": "2024-11-01", "2025-05": "2025-05-01",
    "2026-05": "2026-05-01",
}
REBENCHMARK = {"2015-02", "2019-11", "2024-11"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_data_root(root: Path) -> Path:
    data = root / "data"
    if not (data / "core.json").exists():
        raise FileNotFoundError(f"Missing {data / 'core.json'}")
    editions = {p.stem for p in (data / "ediciones").glob("*.json")}
    if editions != set(EDITION_DATES):
        raise ValueError(f"Unexpected edition set: {sorted(editions)}")
    return data


def apply_migration(conn: psycopg.Connection, migration: Path) -> None:
    sql = migration.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def load_grids(conn: psycopg.Connection, data: Path) -> int:
    payload = load_json(data / "cuadriculas.json")
    rows: list[tuple[str, str, str, str]] = []
    for municipality_code, collection in payload.items():
        for feature in collection.get("features", []):
            props = feature.get("properties", {})
            grid_id = props.get("grid") or props.get("id")
            geometry = feature.get("geometry")
            if not grid_id or not geometry:
                continue
            metadata = {k: v for k, v in props.items() if k not in {"grid", "id"}}
            rows.append((municipality_code, str(grid_id), json.dumps(geometry), json.dumps(metadata)))

    sql = """
        INSERT INTO denue_grid_geometries (municipality_code, grid_id, geom, metadata)
        VALUES (%s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), %s::jsonb)
        ON CONFLICT (municipality_code, grid_id) DO UPDATE
        SET geom = EXCLUDED.geom, metadata = EXCLUDED.metadata
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


def edition_existing_count(conn: psycopg.Connection, edition: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(establishments), 0) FROM denue_observations WHERE source_edition = %s", (edition,))
        return int(cur.fetchone()[0])


def upsert_edition(conn: psycopg.Connection, edition: str, metadata: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO denue_editions
                (source_edition, edition_date, is_rebenchmark, archive_sha256, source_label, metadata)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (source_edition) DO UPDATE SET
                edition_date = EXCLUDED.edition_date,
                is_rebenchmark = EXCLUDED.is_rebenchmark,
                archive_sha256 = EXCLUDED.archive_sha256,
                source_label = EXCLUDED.source_label,
                metadata = EXCLUDED.metadata
            """,
            (
                edition,
                EDITION_DATES[edition],
                edition in REBENCHMARK,
                ARCHIVE_SHA256,
                edition,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )


def replace_edition(conn: psycopg.Connection, edition: str, payload: dict) -> tuple[int, int]:
    municipality_count = 0
    establishment_count = 0
    row_count = 0

    with conn.transaction():
        upsert_edition(conn, edition, {"derived_territorial_panel": True})
        with conn.cursor() as cur:
            cur.execute("DELETE FROM denue_observations WHERE source_edition = %s", (edition,))
            with cur.copy(
                """
                COPY denue_observations
                    (source_edition, municipality_code, ageb, grid_id, sector, size_band, scian6, postal_code, contact_flags, establishments)
                FROM STDIN
                """
            ) as copy:
                for municipality_code, municipal in payload.items():
                    if municipal.get("fields") != EXPECTED_FIELDS:
                        raise ValueError(f"Unexpected schema in {edition}/{municipality_code}: {municipal.get('fields')}")
                    municipality_count += 1
                    municipal_sum = 0
                    for row in municipal.get("rows", []):
                        ageb, grid, sector, size_band, scian6, postal_code, flags, n = row
                        n = int(n)
                        if n <= 0:
                            raise ValueError(f"Non-positive n in {edition}/{municipality_code}: {n}")
                        copy.write_row(
                            (
                                edition,
                                municipality_code,
                                str(ageb),
                                str(grid),
                                str(sector),
                                int(size_band),
                                str(scian6),
                                str(postal_code),
                                int(flags),
                                n,
                            )
                        )
                        row_count += 1
                        municipal_sum += n
                    declared = int(municipal.get("total", 0))
                    if municipal_sum != declared:
                        raise ValueError(
                            f"Total mismatch in {edition}/{municipality_code}: rows={municipal_sum}, declared={declared}"
                        )
                    establishment_count += declared
    return row_count, establishment_count


def verify_database(conn: psycopg.Connection) -> None:
    expected = {"2010": 94_961, "2015-02": 107_458, "2024-11": 135_239, "2026-05": 138_882}
    with conn.cursor() as cur:
        for edition, total in expected.items():
            cur.execute(
                "SELECT COALESCE(SUM(establishments), 0) FROM denue_observations WHERE source_edition = %s",
                (edition,),
            )
            actual = int(cur.fetchone()[0])
            if actual != total:
                raise ValueError(f"Database smoke total mismatch for {edition}: {actual} != {total}")
        cur.execute(
            """
            SELECT COALESCE(SUM(establishments), 0)
            FROM denue_observations
            WHERE source_edition = '2026-05' AND municipality_code = '25_012'
            """
        )
        mazatlan = int(cur.fetchone()[0])
        if mazatlan != 27_487:
            raise ValueError(f"Mazatlán 2026-05 mismatch: {mazatlan} != 27487")


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the audited aggregated DENUE historical panel into PostgreSQL/PostGIS.")
    parser.add_argument("--root", type=Path, default=Path("var/denue/extracted"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--migration", type=Path, default=Path("packages/db/migrations/003_denue.sql"))
    parser.add_argument("--apply-migration", action="store_true")
    parser.add_argument("--replace", action="store_true", help="Replace editions already present in the database.")
    parser.add_argument("--skip-grids", action="store_true")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")
    data = validate_data_root(args.root)

    with psycopg.connect(args.database_url) as conn:
        if args.apply_migration:
            apply_migration(conn, args.migration)
        if not args.skip_grids:
            grids = load_grids(conn, data)
            print(f"Upserted {grids:,} municipality-grid geometries")

        for edition in sorted(EDITION_DATES, key=lambda key: EDITION_DATES[key]):
            current = edition_existing_count(conn, edition)
            if current and not args.replace:
                print(f"skip {edition}: already stores {current:,} establishments")
                continue
            payload = load_json(data / "ediciones" / f"{edition}.json")
            rows, establishments = replace_edition(conn, edition, payload)
            print(f"loaded {edition}: {rows:,} grouped rows / {establishments:,} establishments")

        verify_database(conn)
        print("Database smoke totals verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
