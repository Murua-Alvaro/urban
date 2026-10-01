from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from .ingestion import ingest_zip
from .normalization import normalize_asset
from .repository import persist_manifest

app = FastAPI(title="Urban API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class NormalizeRequest(BaseModel):
    asset_path: str


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
        canonical_dataset_id = persist_manifest(manifest)
        payload = asdict(manifest)
        payload["dataset_id"] = canonical_dataset_id
        return {
            "status": "persisted",
            "dataset": payload,
            "next": "normalize one or more tabular assets into the canonical Urban schema",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Dataset validated but database persistence failed") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@app.post("/v1/datasets/{dataset_id}/normalize")
def normalize_dataset_asset(dataset_id: str, request: NormalizeRequest) -> dict:
    try:
        report = normalize_asset(dataset_id, request.asset_path)
        return {"status": "normalized", "report": asdict(report)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Normalization completed but persistence failed") from exc
