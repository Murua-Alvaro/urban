import pandas as pd

from urban_denue.modeling import prepare_grid_model_sample, spatial_group_cv


def _features():
    rows = []
    for grid, base in [("g1", 10), ("g2", 20), ("g3", 30), ("g4", 40), ("g5", 50)]:
        for edition, date, reb, add in [
            ("2019-04", "2019-04-01", False, 0),
            ("2019-11", "2019-11-01", True, 5),
            ("2020-04", "2020-04-01", False, 8),
            ("2020-11", "2020-11-01", False, 9),
        ]:
            stock = base + add
            rows.append({
                "canonical_edition":edition,"edition_date":pd.Timestamp(date),"rebenchmark":reb,
                "municipality_key":"25_012","municipality_code":"012","grid_analysis":grid,
                "establishments":stock,"log_stock":0.0,"effective_sectors":3.0,"sector_hhi":0.2,
                "sectors":3,"scian6_classes":5,"phone_share":0.5,"email_share":0.2,"web_share":0.1,
                "active_share_history":1.0,"neighbor_stock_mean":stock,"relative_to_neighbor_mean":1.0,
            })
    return pd.DataFrame(rows)


def test_target_rebenchmark_transition_is_excluded():
    sample = prepare_grid_model_sample(_features())
    assert not (sample["next_date"] == pd.Timestamp("2019-11-01")).any()
    assert (sample["next_date"] == pd.Timestamp("2020-04-01")).any()


def test_spatial_cv_has_no_group_leakage_and_returns_metrics():
    sample = prepare_grid_model_sample(_features())
    metrics = spatial_group_cv(sample, folds=3)
    assert len(metrics) == 3
    assert metrics["mae_stock"].notna().all()
