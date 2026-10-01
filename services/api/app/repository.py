from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import text

from .db import engine
from .ingestion import IngestionManifest


def persist_manifest(manifest: IngestionManifest) -> str:
    """Persist an ingestion manifest idempotently by SHA-256.

    Returns the canonical dataset UUID stored in Postgres. Re-uploading the same
    ZIP reuses the dataset record and refreshes asset metadata without creating a
    second logical dataset.
    """
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO datasets(name, source_type, original_filename, sha256, status, metadata)
                VALUES (:name, 'zip_upload', :filename, :sha256, 'validated', CAST(:metadata AS jsonb))
                ON CONFLICT (sha256) DO UPDATE SET
                    original_filename = EXCLUDED.original_filename,
                    status = 'validated',
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "name": manifest.original_name,
                "filename": manifest.original_name,
                "sha256": manifest.sha256,
                "metadata": '{"ingestion_version":"0.1.0"}',
            },
        ).mappings().one()
        dataset_id = str(row["id"])

        for asset in manifest.assets:
            conn.execute(
                text(
                    """
                    INSERT INTO dataset_assets(dataset_id, path, extension, size_bytes, row_count, columns, metadata)
                    VALUES (CAST(:dataset_id AS uuid), :path, :extension, :size_bytes, :row_count, CAST(:columns AS jsonb), '{}'::jsonb)
                    ON CONFLICT (dataset_id, path) DO UPDATE SET
                        extension = EXCLUDED.extension,
                        size_bytes = EXCLUDED.size_bytes,
                        row_count = EXCLUDED.row_count,
                        columns = EXCLUDED.columns
                    """
                ),
                {
                    "dataset_id": dataset_id,
                    "path": asset.path,
                    "extension": asset.extension,
                    "size_bytes": asset.size_bytes,
                    "row_count": asset.rows,
                    "columns": __import__("json").dumps(asset.columns or []),
                },
            )

        conn.execute(
            text(
                """
                INSERT INTO ingestion_events(dataset_id, stage, status, message, payload)
                VALUES (CAST(:dataset_id AS uuid), 'zip_validation', 'success', :message, CAST(:payload AS jsonb))
                """
            ),
            {
                "dataset_id": dataset_id,
                "message": f"Validated {len(manifest.assets)} supported assets",
                "payload": __import__("json").dumps(asdict(manifest)),
            },
        )

    return dataset_id
