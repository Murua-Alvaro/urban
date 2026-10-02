import pandas as pd

from urban_denue.spatial_eda import grid_panel, polycentricity_summary


def _frame():
    rows = []
    for edition, date, values in [("2025-05", "2025-05-01", {"g1": 8, "g2": 2}), ("2026-05", "2026-05-01", {"g1": 10, "g3": 3})]:
        for grid, n in values.items():
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


def test_new_municipality_is_not_backfilled_before_its_first_denue_edition():
    old = pd.DataFrame([
        {"canonical_edition":"2024-11","edition_date":pd.Timestamp("2024-11-01"),"rebenchmark":True,"municipality_key":"25_012","municipality_code":"012","municipality_name":"Mazatlan","grid_analysis":"g1","establishments":10},
        {"canonical_edition":"2025-05","edition_date":pd.Timestamp("2025-05-01"),"rebenchmark":False,"municipality_key":"25_012","municipality_code":"012","municipality_name":"Mazatlan","grid_analysis":"g1","establishments":11},
    ])
    new = pd.DataFrame([
        {"canonical_edition":"2025-05","edition_date":pd.Timestamp("2025-05-01"),"rebenchmark":False,"municipality_key":"25_019","municipality_code":"019","municipality_name":"Eldorado","grid_analysis":"e1","establishments":4},
        {"canonical_edition":"2026-05","edition_date":pd.Timestamp("2026-05-01"),"rebenchmark":False,"municipality_key":"25_019","municipality_code":"019","municipality_name":"Eldorado","grid_analysis":"e1","establishments":5},
    ])
    panel = grid_panel(pd.concat([old, new], ignore_index=True))
    eldorado = panel.loc[panel["municipality_code"].eq("019")]
    assert list(eldorado["canonical_edition"]) == ["2025-05", "2026-05"]
    assert eldorado["lag_establishments"].isna().iloc[0]
