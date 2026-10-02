from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "denue" / "panel.py"
spec = importlib.util.spec_from_file_location("denue_panel", MODULE_PATH)
panel = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(panel)


def test_payload_is_weighted_and_flags_are_decoded() -> None:
    payload = {
        "fields": ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"],
        "rows": [
            ["0120", "12-700-2855", "11", 1, "112511", "81220", 7, 3],
            ["SIN_AGEB", "SIN_GRID", "72", 0, "722511", "SIN_CP", 0, 2],
        ],
        "total": 5,
    }
    meta = {"state_code": "25", "state": "Sinaloa", "mun_code": "012", "name": "Mazatlán"}
    df = panel.municipality_payload_to_frame("2026-05", "25_012", payload, meta)

    assert int(df["establishments"].sum()) == 5
    assert bool(df.loc[0, "has_phone"])
    assert bool(df.loc[0, "has_email"])
    assert bool(df.loc[0, "has_web"])
    assert bool(df.loc[1, "missing_ageb"])
    assert bool(df.loc[1, "missing_grid"])
    assert bool(df.loc[1, "missing_postal_code"])


def test_declared_total_must_match_rows() -> None:
    payload = {
        "fields": ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"],
        "rows": [["0120", "g", "11", 1, "112511", "81220", 0, 2]],
        "total": 99,
    }
    meta = {"state_code": "25", "state": "Sinaloa", "mun_code": "012", "name": "Mazatlán"}
    with pytest.raises(ValueError, match="Total mismatch"):
        panel.municipality_payload_to_frame("2026-05", "25_012", payload, meta)
