from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EditionAsset:
    source_edition: str
    path: Path


def data_root(extracted_root: Path) -> Path:
    direct = extracted_root / "data"
    if (direct / "core.json").exists():
        return direct
    matches = list(extracted_root.rglob("core.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected exactly one core.json under {extracted_root}; found {len(matches)}")
    return matches[0].parent


def load_core(extracted_root: Path) -> dict:
    return json.loads((data_root(extracted_root) / "core.json").read_text(encoding="utf-8"))


def municipality_catalog(extracted_root: Path) -> dict[str, dict]:
    core = load_core(extracted_root)
    return core["manifest"]["municipalities"]


def edition_assets(extracted_root: Path) -> list[EditionAsset]:
    folder = data_root(extracted_root) / "ediciones"
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    return [EditionAsset(p.stem, p) for p in sorted(folder.glob("*.json"))]


def load_edition_payload(asset: EditionAsset) -> dict:
    payload = json.loads(asset.path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"edition {asset.source_edition} must be a JSON object")
    return payload
