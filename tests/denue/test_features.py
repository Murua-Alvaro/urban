import pandas as pd

from urban_denue.features import add_temporal_features, geography_sector_lq


def test_temporal_features_exclude_rebenchmark_transition():
    panel = pd.DataFrame([
        {"canonical_edition":"2019-04","edition_date":pd.Timestamp("2019-04-01"),"rebenchmark":False,"transition_rebenchmark":False,"municipality_key":"25_012","municipality_code":"012","municipality_name":"Mazatlan","grid_analysis":"g1","establishments":10,"pct_change":None,"active":True,"first_active_date":pd.Timestamp("2019-04-01")},
        {"canonical_edition":"2019-11","edition_date":pd.Timestamp("2019-11-01"),"rebenchmark":True,"transition_rebenchmark":True,"municipality_key":"25_012","municipality_code":"012","municipality_name":"Mazatlan","grid_analysis":"g1","establishments":15,"pct_change":50.0,"active":True,"first_active_date":pd.Timestamp("2019-04-01")},
    ])
    out = add_temporal_features(panel, "grid_analysis")
    assert pd.isna(out.iloc[1]["growth_pct_clean"])
    assert not bool(out.iloc[1]["model_transition_ok"])


def test_geography_sector_lq_detects_specialization():
    frame = pd.DataFrame([
        {"canonical_edition":"x","edition_date":pd.Timestamp("2026-01-01"),"municipality_key":"m","municipality_code":"001","municipality_name":"M","grid_analysis":"g1","sector":"72","establishments":8},
        {"canonical_edition":"x","edition_date":pd.Timestamp("2026-01-01"),"municipality_key":"m","municipality_code":"001","municipality_name":"M","grid_analysis":"g1","sector":"54","establishments":2},
        {"canonical_edition":"x","edition_date":pd.Timestamp("2026-01-01"),"municipality_key":"m","municipality_code":"001","municipality_name":"M","grid_analysis":"g2","sector":"72","establishments":2},
        {"canonical_edition":"x","edition_date":pd.Timestamp("2026-01-01"),"municipality_key":"m","municipality_code":"001","municipality_name":"M","grid_analysis":"g2","sector":"54","establishments":8},
    ])
    out = geography_sector_lq(frame, "grid_analysis")
    row = out.loc[(out["grid_analysis"] == "g1") & (out["sector"] == "72")].iloc[0]
    assert row["location_quotient"] > 1
