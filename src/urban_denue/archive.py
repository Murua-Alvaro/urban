from __future__ import annotations

import hashlib
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from .constants import ARCHIVE_SHA256, ARCHIVE_SIZE, ARCHIVE_URL


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != ARCHIVE_SIZE:
        raise ValueError(f"archive size mismatch: {path.stat().st_size} != {ARCHIVE_SIZE}")
    digest = sha256_file(path)
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"archive SHA-256 mismatch: {digest} != {ARCHIVE_SHA256}")
    if not zipfile.is_zipfile(path):
        raise ValueError("archive is not a valid ZIP")


def acquire_archive(destination: Path, url: str = ARCHIVE_URL, force: bool = False) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        try:
            verify_archive(destination)
            return destination
        except (OSError, ValueError):
            pass

    tmp = destination.with_suffix(destination.suffix + ".part")
    tmp.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "urban-denue/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
        verify_archive(tmp)
        tmp.replace(destination)
    except urllib.error.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        if exc.code == 404:
            raise FileNotFoundError(
                "DENUE archive is not yet present in GitHub at: "
                f"{url}. Upload the audited ZIP to data/denue/raw/ on branch "
                "data/denue-historico, or use the Colab notebook manual-upload fallback."
            ) from exc
        raise
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return destination


def safe_extract(archive: Path, destination: Path, force: bool = False) -> Path:
    verify_archive(archive)
    marker = destination / ".archive_sha256"
    if destination.exists() and marker.exists() and not force:
        if marker.read_text(encoding="utf-8").strip() == ARCHIVE_SHA256:
            return destination
    if force and destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(f"unsafe ZIP member: {info.filename}")
            target = (destination / Path(*member.parts)).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"ZIP member escapes destination: {info.filename}")
            mode = info.external_attr >> 16
            if mode & 0o120000 == 0o120000:
                raise ValueError(f"symlink ZIP member not allowed: {info.filename}")
        zf.extractall(destination)
    marker.write_text(ARCHIVE_SHA256 + "\n", encoding="utf-8")
    return destination
