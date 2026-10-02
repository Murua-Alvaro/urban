import pandas as pd

from urban_denue.spatial_eda import grid_panel, polycentricity_summary


def _frame():
    rows = []
    for edition, date, values in [("2025-05", "2025-05-01", {"g1": 8, "g2": 2}), ("2026-05", "2026-05-01", {"g1": 10, "g2": 0, "g3": 3})]:
        for grid, n in values.items():
            if n == 0:
                continue
            rows.append({"canonical_edition":edition,"edition_date":pd.Timestamp(date),"rebenchmark":False,"municipality_key":"25_012","municipality_code":"012","municipality_name":"Mazatlan","grid_analysis":grid,"establishments":n})
    return pd.DataFrame(rows)


def test_grid_panel_fills_zero_and_marks_appearance():
    panel = grid_panel(_frame())
    g3 = panel.loc[panel["grid_analysis"].eq("g3")].sort_values("edition_date")
    assert list(g3["establishments"]) == [0, 3]
    assert bool(g3.iloc[1]["appearance_proxy"])


def test_polycentricity_top_share():
    panel = grid_panel(_frame())
    summary = polycentricity_summary(panel)
    first = summary.sort_values("edition_date").iloc[0]
    assert round(first["top1_share"], 6) == 0.8
