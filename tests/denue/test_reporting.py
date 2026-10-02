from pathlib import Path
import pandas as pd

from urban_denue.reporting import municipality_report


def test_municipality_report_contains_methodological_caveat(tmp_path: Path):
    core = tmp_path / "processed" / "eda_core"
    spatial = tmp_path / "processed" / "spatial_eda"
    core.mkdir(parents=True)
    spatial.mkdir(parents=True)
    pd.DataFrame([
        {"canonical_edition":"2025-05","edition_date":pd.Timestamp("2025-05-01"),"rebenchmark":False,"municipality_code":"012","municipality_name":"Mazatlan","establishments":10,"state_share":0.1},
        {"canonical_edition":"2026-05","edition_date":pd.Timestamp("2026-05-01"),"rebenchmark":False,"municipality_code":"012","municipality_name":"Mazatlan","establishments":12,"state_share":0.11},
    ]).to_parquet(core / "municipality_timeseries.parquet", index=False)
    pd.DataFrame([
        {"canonical_edition":"2026-05","edition_date":pd.Timestamp("2026-05-01"),"municipality_code":"012","municipality_name":"Mazatlan","sector":"72","establishments":12,"local_share":1.0,"location_quotient":1.2}
    ]).to_parquet(core / "municipality_sector.parquet", index=False)
    pd.DataFrame([
        {"canonical_edition":"2026-05","municipality_code":"012","active_grids":3,"top1_share":0.5,"top10_share":1.0,"effective_hhi_grids":2.5,"grid_gini":0.2}
    ]).to_parquet(spatial / "polycentricity.parquet", index=False)
    report = municipality_report(tmp_path / "processed", tmp_path / "reports", "012")
    text = report.read_text(encoding="utf-8")
    assert "stock registrado" in text
    assert "No deben interpretarse automáticamente" in text
