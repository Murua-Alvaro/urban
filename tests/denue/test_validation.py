import json
from pathlib import Path

from urban_denue.validation import validate_extracted


def _fixture(tmp_path: Path, rows, total):
    root = tmp_path / "data"
    (root / "ediciones").mkdir(parents=True)
    core = {"manifest": {"municipalities": {"25_012": {"name": "Mazatlan"}}}}
    (root / "core.json").write_text(json.dumps(core), encoding="utf-8")
    edition = {"25_012": {"fields": ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"], "rows": rows, "total": total}}
    (root / "ediciones" / "2026-05.json").write_text(json.dumps(edition), encoding="utf-8")


def test_validation_accepts_consistent_grouped_data(tmp_path: Path):
    _fixture(tmp_path, [["0120", "g1", "11", 1, "112511", "82000", 1, 2]], 2)
    report = validate_extracted(tmp_path)
    assert not report.errors
    assert report.establishments == 2


def test_validation_detects_total_mismatch(tmp_path: Path):
    _fixture(tmp_path, [["0120", "g1", "11", 1, "112511", "82000", 1, 2]], 3)
    report = validate_extracted(tmp_path)
    assert any(issue.code == "total_mismatch" for issue in report.errors)
