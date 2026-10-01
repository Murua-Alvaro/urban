from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from .ingestion import ingest_zip

app = FastAPI(title="Urban API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/datasets/upload")
def upload_dataset(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "dataset.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=415, detail="Only ZIP uploads are accepted")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp:
            temp_path = Path(temp.name)
            shutil.copyfileobj(file.file, temp)

        manifest = ingest_zip(temp_path, filename)
        return {
            "status": "ingested",
            "dataset": asdict(manifest),
            "next": "map fields to canonical Urban schema",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
