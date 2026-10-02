from __future__ import annotations

import hashlib
import json
import shutil
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from .config import settings


@dataclass(slots=True)
class AssetProfile:
    path: str
    size_bytes: int
    extension: str
    rows: int | None = None
    columns: list[str] | None = None


@dataclass(slots=True)
class IngestionManifest:
    dataset_id: str
    original_name: str
    sha256: str
    archive_bytes: int
    assets: list[AssetProfile]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member_path(root: Path, member_name: str) -> Path:
    destination = (root / member_name).resolve()
    if root.resolve() not in destination.parents and destination != root.resolve():
        raise ValueError(f"Unsafe ZIP path: {member_name}")
    return destination


def _profile_asset(path: Path, relative: str) -> AssetProfile:
    ext = path.suffix.lower()
    profile = AssetProfile(path=relative, size_bytes=path.stat().st_size, extension=ext)

    try:
        if ext == ".csv":
            frame = pd.read_csv(path, nrows=10_000)
            profile.columns = [str(col) for col in frame.columns]
        elif ext == ".parquet":
            parquet = pq.ParquetFile(path)
            profile.rows = parquet.metadata.num_rows
            profile.columns = parquet.schema.names
        elif ext == ".xlsx":
            frame = pd.read_excel(path, nrows=10_000)
            profile.columns = [str(col) for col in frame.columns]
    except Exception:
        # Profiling is diagnostic; ingestion should retain the asset for later validation.
        pass

    return profile


def _read_existing_manifest(path: Path) -> IngestionManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return IngestionManifest(
        dataset_id=payload["dataset_id"],
        original_name=payload["original_name"],
        sha256=payload["sha256"],
        archive_bytes=payload["archive_bytes"],
        assets=[AssetProfile(**asset) for asset in payload["assets"]],
    )


def ingest_zip(upload_path: Path, original_name: str) -> IngestionManifest:
    if upload_path.stat().st_size > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"Upload exceeds {settings.max_upload_mb} MB limit")
    if not zipfile.is_zipfile(upload_path):
        raise ValueError("Uploaded file is not a valid ZIP archive")

    checksum = sha256_file(upload_path)
    dataset_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"urban:sha256:{checksum}"))
    dataset_root = settings.data_dir / dataset_id
    manifest_path = dataset_root / "manifest.json"
    if manifest_path.exists():
        return _read_existing_manifest(manifest_path)

    raw_root = dataset_root / "raw"
    raw_root.mkdir(parents=True, exist_ok=False)

    assets: list[AssetProfile] = []
    try:
        with zipfile.ZipFile(upload_path) as archive:
            total_uncompressed = sum(member.file_size for member in archive.infolist() if not member.is_dir())
            if total_uncompressed > settings.max_uncompressed_mb * 1024 * 1024:
                raise ValueError(
                    f"Archive expands beyond {settings.max_uncompressed_mb} MB safety limit"
                )

            for member in archive.infolist():
                if member.is_dir():
                    continue
                suffix = Path(member.filename).suffix.lower()
                if suffix not in settings.allowed_extensions:
                    continue
                destination = _safe_member_path(raw_root, member.filename)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
                assets.append(_profile_asset(destination, member.filename))

        if not assets:
            raise ValueError("ZIP contains no supported data assets")

        manifest = IngestionManifest(
            dataset_id=dataset_id,
            original_name=original_name,
            sha256=checksum,
            archive_bytes=upload_path.stat().st_size,
            assets=assets,
        )
        manifest_path.write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest
    except Exception:
        shutil.rmtree(dataset_root, ignore_errors=True)
        raise
