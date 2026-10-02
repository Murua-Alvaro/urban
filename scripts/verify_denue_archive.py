from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/denue/manifests/Growa_DENUE_Sinaloa_Historico_2010_2026.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    archive = ROOT / manifest["expected_repository_path"]
    if not archive.exists():
        raise SystemExit(f"DENUE archive missing: {archive}")

    actual_size = archive.stat().st_size
    actual_sha = sha256_file(archive)
    expected_size = int(manifest["archive_size_bytes"])
    expected_sha = str(manifest["sha256"])

    if actual_size != expected_size:
        raise SystemExit(f"Size mismatch: expected {expected_size}, got {actual_size}")
    if actual_sha != expected_sha:
        raise SystemExit(f"SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")

    print(f"OK: {archive.name}")
    print(f"bytes={actual_size}")
    print(f"sha256={actual_sha}")


if __name__ == "__main__":
    main()
