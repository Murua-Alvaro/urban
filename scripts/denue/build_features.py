from __future__ import annotations

import argparse
import json
import pandas as pd

from urban_denue.config import ensure_dirs, paths
from urban_denue.eda import load_staged
from urban_denue.features import build_model_features, geography_sector_lq, queen_neighbor_features, write_feature_store
from urban_denue.spatial_eda import add_grid_area, ageb_panel, geography_diversity, grid_panel, load_grid_geometry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DENUE feature store for downstream econometrics")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    p = paths(args.root)
    ensure_dirs(p)
    frame = load_staged(p.staged)
    grids = grid_panel(frame)
    agebs = ageb_panel(frame)
    grid_div = geography_diversity(frame, "grid_analysis")
    ageb_div = geography_diversity(frame, "ageb_analysis")
    geometry = add_grid_area(load_grid_geometry(p.extracted))

    grid_features = build_model_features(frame, grids, grid_div, "grid_analysis")
    grid_features = queen_neighbor_features(grid_features, geometry)
    ageb_features = build_model_features(frame, agebs, ageb_div, "ageb_analysis")
    grid_lq = geography_sector_lq(frame, "grid_analysis")
    ageb_lq = geography_sector_lq(frame, "ageb_analysis")

    outputs = write_feature_store({
        "grid_features": grid_features,
        "ageb_features": ageb_features,
        "grid_sector_lq": grid_lq,
        "ageb_sector_lq": ageb_lq,
    }, p.processed / "feature_store")
    report = {
        "outputs": outputs,
        "grid_feature_rows": int(len(grid_features)),
        "ageb_feature_rows": int(len(ageb_features)),
        "econometric_ready_grid_transitions": int(grid_features["model_transition_ok"].sum()),
        "econometric_ready_ageb_transitions": int(ageb_features["model_transition_ok"].sum()),
    }
    (p.reports / "feature_store.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
