from pathlib import Path
import zipfile

import pytest

from urban_denue.archive import safe_extract


def test_safe_extract_rejects_parent_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "bad")
    monkeypatch.setattr("urban_denue.archive.verify_archive", lambda _: None)
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        safe_extract(archive, tmp_path / "out")
