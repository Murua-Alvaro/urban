import json
from pathlib import Path

from urban_denue.catalog import edition_assets
from urban_denue.cleaning import clean_asset


def _build(tmp_path: Path):
    root = tmp_path / "data"
    (root / "ediciones").mkdir(parents=True)
    (root / "core.json").write_text(json.dumps({"manifest": {"municipalities": {"25_012": {"name": "Mazatlan", "mun_code": "12"}}}}), encoding="utf-8")
    payload = {"25_012": {"fields": ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"], "rows": [["0120", "g1", "11", 1, "112511", "82000", 7, 3]], "total": 3}}
    (root / "ediciones" / "2015-02.json").write_text(json.dumps(payload), encoding="utf-8")


def test_cleaning_preserves_source_and_canonicalizes_edition(tmp_path: Path):
    _build(tmp_path)
    asset = edition_assets(tmp_path)[0]
    result = clean_asset(tmp_path, asset)
    row = result.frame.iloc[0]
    assert row["source_edition"] == "2015-02"
    assert row["canonical_edition"] == "2015-01"
    assert bool(row["has_phone"]) and bool(row["has_email"]) and bool(row["has_web"])
    assert row["municipality_code"] == "012"
