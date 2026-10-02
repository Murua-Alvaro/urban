from __future__ import annotations

import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "denue" / "fetch_archive.py"
spec = importlib.util.spec_from_file_location("fetch_archive", MODULE_PATH)
loader = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(loader)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_validate_and_extract_verified_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("data/ediciones/2026-05.json", '{"25_012":{"fields":[],"rows":[],"total":0}}')
    monkeypatch.setattr(loader, "EXPECTED_SIZE", archive.stat().st_size)
    monkeypatch.setattr(loader, "EXPECTED_SHA256", _sha(archive))

    loader.validate_archive(archive)
    out = loader.safe_extract(archive, tmp_path / "out")
    assert (out / "data/ediciones/2026-05.json").exists()
    assert (out / ".archive_sha256").read_text().strip() == _sha(archive)


def test_safe_extract_rejects_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "no")
    monkeypatch.setattr(loader, "EXPECTED_SIZE", archive.stat().st_size)
    monkeypatch.setattr(loader, "EXPECTED_SHA256", _sha(archive))

    with pytest.raises(ValueError, match="Unsafe ZIP member"):
        loader.safe_extract(archive, tmp_path / "out")
