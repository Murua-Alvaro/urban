from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ARCHIVE_NAME = "Growa_DENUE_Sinaloa_Historico_2010_2026.zip"
EXPECTED_SHA256 = "182c22a2a96189e47d4e0d6b5dfd2a34a09307cfa3af57b1503664cdecc1bff3"
EXPECTED_SIZE = 14_147_652
DEFAULT_BRANCH = "data/denue-historico"
DEFAULT_URL = (
    "https://raw.githubusercontent.com/Murua-Alvaro/urban/"
    f"{DEFAULT_BRANCH}/data/denue/raw/{ARCHIVE_NAME}"
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if size != EXPECTED_SIZE:
        raise ValueError(f"Unexpected archive size: {size:,} bytes; expected {EXPECTED_SIZE:,}")
    digest = sha256_file(path)
    if digest != EXPECTED_SHA256:
        raise ValueError(f"SHA-256 mismatch: {digest} != {EXPECTED_SHA256}")
    if not zipfile.is_zipfile(path):
        raise ValueError("Downloaded file is not a valid ZIP archive")


def download_archive(destination: Path, url: str = DEFAULT_URL, force: bool = False) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        try:
            validate_archive(destination)
            print(f"Using cached verified archive: {destination}")
            return destination
        except (ValueError, OSError):
            print("Cached archive failed verification; downloading a clean copy.")

    tmp = destination.with_suffix(destination.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "urban-denue-loader/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    validate_archive(tmp)
    tmp.replace(destination)
    print(f"Downloaded and verified: {destination}")
    return destination


def safe_extract(archive: Path, destination: Path, force: bool = False) -> Path:
    validate_archive(archive)
    marker = destination / ".archive_sha256"
    if destination.exists() and marker.exists() and marker.read_text().strip() == EXPECTED_SHA256 and not force:
        print(f"Using cached extraction: {destination}")
        return destination

    if force and destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(f"Unsafe ZIP member: {info.filename}")
            target = (destination / Path(*member.parts)).resolve()
            if root not in target.parents and target != root:
                raise ValueError(f"ZIP path escapes destination: {info.filename}")
        zf.extractall(destination)
    marker.write_text(EXPECTED_SHA256 + "\n", encoding="utf-8")
    print(f"Extracted verified archive to: {destination}")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Download, verify and optionally extract the audited DENUE archive.")
    parser.add_argument("--archive", type=Path, default=Path("var/denue") / ARCHIVE_NAME)
    parser.add_argument("--extract-to", type=Path, default=Path("var/denue/extracted"))
    parser.add_argument("--url", default=os.getenv("DENUE_ARCHIVE_URL", DEFAULT_URL))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()

    try:
        archive = download_archive(args.archive, url=args.url, force=args.force)
        if args.extract:
            safe_extract(archive, args.extract_to, force=args.force)
    except Exception as exc:
        print(f"DENUE loader failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
