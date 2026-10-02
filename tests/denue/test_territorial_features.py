from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "denue" / "territorial_features.py"
spec = importlib.util.spec_from_file_location("territorial_features", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_grid_balancing_respects_municipality_observed_editions() -> None:
    features = pd.DataFrame(
        [
            {"source_edition": "2024-11", "edition_date": pd.Timestamp("2024-11-01"), "municipality_code": "25_001", "municipality_name": "Old", "grid": "g1", "establishments": 3, "sector_count": 1, "scian6_count": 1, "sector_hhi": 1.0, "sector_shannon": 0.0, "effective_sectors": 1.0, "phone_share": 0.5, "email_share": 0.0, "web_share": 0.0},
            {"source_edition": "2025-05", "edition_date": pd.Timestamp("2025-05-01"), "municipality_code": "25_001", "municipality_name": "Old", "grid": "g1", "establishments": 4, "sector_count": 1, "scian6_count": 1, "sector_hhi": 1.0, "sector_shannon": 0.0, "effective_sectors": 1.0, "phone_share": 0.5, "email_share": 0.0, "web_share": 0.0},
            {"source_edition": "2025-05", "edition_date": pd.Timestamp("2025-05-01"), "municipality_code": "25_019", "municipality_name": "New", "grid": "g9", "establishments": 2, "sector_count": 1, "scian6_count": 1, "sector_hhi": 1.0, "sector_shannon": 0.0, "effective_sectors": 1.0, "phone_share": 0.5, "email_share": 0.0, "web_share": 0.0},
        ]
    )

    out = mod.add_grid_dynamics(features)
    new_municipality = out.loc[out["municipality_code"].eq("25_019")]
    assert set(new_municipality["source_edition"]) == {"2025-05"}
    assert len(new_municipality) == 1
    assert new_municipality.iloc[0]["transition"] == "first_observation"


def test_fixed_grid_can_activate_within_existing_municipality_history() -> None:
    features = pd.DataFrame(
        [
            {"source_edition": "2024-11", "edition_date": pd.Timestamp("2024-11-01"), "municipality_code": "25_012", "municipality_name": "Mazatlán", "grid": "g1", "establishments": 5, "sector_count": 1, "scian6_count": 1, "sector_hhi": 1.0, "sector_shannon": 0.0, "effective_sectors": 1.0, "phone_share": 0.5, "email_share": 0.0, "web_share": 0.0},
            {"source_edition": "2025-05", "edition_date": pd.Timestamp("2025-05-01"), "municipality_code": "25_012", "municipality_name": "Mazatlán", "grid": "g1", "establishments": 5, "sector_count": 1, "scian6_count": 1, "sector_hhi": 1.0, "sector_shannon": 0.0, "effective_sectors": 1.0, "phone_share": 0.5, "email_share": 0.0, "web_share": 0.0},
            {"source_edition": "2025-05", "edition_date": pd.Timestamp("2025-05-01"), "municipality_code": "25_012", "municipality_name": "Mazatlán", "grid": "g2", "establishments": 2, "sector_count": 1, "scian6_count": 1, "sector_hhi": 1.0, "sector_shannon": 0.0, "effective_sectors": 1.0, "phone_share": 0.5, "email_share": 0.0, "web_share": 0.0},
        ]
    )

    out = mod.add_grid_dynamics(features)
    g2 = out.loc[out["grid"].eq("g2")].sort_values("edition_date")
    assert list(g2["establishments"]) == [0, 2]
    assert list(g2["transition"]) == ["first_observation", "activation"]
