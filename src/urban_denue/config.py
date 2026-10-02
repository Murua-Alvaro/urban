from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class DenuePaths:
    root: Path
    archive: Path
    extracted: Path
    staged: Path
    processed: Path
    reports: Path


def paths(root: str | Path | None = None) -> DenuePaths:
    base = Path(root or os.getenv("URBAN_DENUE_HOME", "var/denue")).expanduser().resolve()
    return DenuePaths(
        root=base,
        archive=base / "raw" / "Growa_DENUE_Sinaloa_Historico_2010_2026.zip",
        extracted=base / "extracted",
        staged=base / "staged",
        processed=base / "processed",
        reports=base / "reports",
    )


def ensure_dirs(p: DenuePaths) -> None:
    for folder in (p.archive.parent, p.extracted, p.staged, p.processed, p.reports):
        folder.mkdir(parents=True, exist_ok=True)
