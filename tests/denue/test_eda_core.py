import pandas as pd

from urban_denue.eda import edition_summary, sector_summary


def _frame():
    return pd.DataFrame([
        {"canonical_edition":"2025-05","edition_date":pd.Timestamp("2025-05-01"),"rebenchmark":False,"municipality_code":"012","municipality_name":"Mazatlan","sector":"72","size_band":1,"establishments":8,"missing_ageb":False,"missing_grid":False,"ageb_analysis":"a","grid_analysis":"g","has_phone":True,"has_email":False,"has_web":True,"postal_status":"valid_plausible"},
        {"canonical_edition":"2025-05","edition_date":pd.Timestamp("2025-05-01"),"rebenchmark":False,"municipality_code":"012","municipality_name":"Mazatlan","sector":"54","size_band":1,"establishments":2,"missing_ageb":False,"missing_grid":False,"ageb_analysis":"b","grid_analysis":"h","has_phone":False,"has_email":False,"has_web":False,"postal_status":"valid_plausible"},
    ])


def test_edition_summary_weighted_total_and_contact_share():
    out = edition_summary(_frame()).iloc[0]
    assert out["establishments"] == 10
    assert out["phone_share"] == 0.8


def test_location_quotient_is_one_with_single_municipality():
    out = sector_summary(_frame())
    assert (out["location_quotient"].round(8) == 1).all()
