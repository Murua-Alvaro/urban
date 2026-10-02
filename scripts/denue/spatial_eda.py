from __future__ import annotations

import argparse
import json

from urban_denue.config import ensure_dirs, paths
from urban_denue.eda import load_staged
from urban_denue.spatial_eda import (
    add_grid_area, ageb_panel, geography_diversity, global_moran_by_municipality,
    grid_panel, load_grid_geometry, polycentricity_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build spatial DENUE EDA artifacts")
    parser.add_argument("--root", default=None)
    parser.add_argument("--skip-moran", action="store_true")
    args = parser.parse_args()
    p = paths(args.root)
    ensure_dirs(p)
    frame = load_staged(p.staged)
    output = p.processed / "spatial_eda"
    output.mkdir(parents=True, exist_ok=True)

    grids = grid_panel(frame)
    agebs = ageb_panel(frame)
    grid_diversity = geography_diversity(frame, "grid_analysis")
    ageb_diversity = geography_diversity(frame, "ageb_analysis")
    poly = polycentricity_summary(grids)
    geometry = add_grid_area(load_grid_geometry(p.extracted))
    grids_geo = grids.merge(geometry.drop(columns="geometry"), on=["municipality_key", "grid_analysis"], how="left")
    grids_geo["establishments_per_km2"] = grids_geo["establishments"] / grids_geo["area_km2"].replace(0, float("nan"))

    artifacts = {
        "grid_panel": grids_geo,
        "ageb_panel": agebs,
        "grid_diversity": grid_diversity,
        "ageb_diversity": ageb_diversity,
        "polycentricity": poly,
    }
    outputs = {}
    for name, data in artifacts.items():
        target = output / f"{name}.parquet"
        data.to_parquet(target, index=False)
        outputs[name] = str(target)
    geom_target = output / "grid_geometry.parquet"
    geometry.to_parquet(geom_target, index=False)
    outputs["grid_geometry"] = str(geom_target)

    if not args.skip_moran:
        moran = global_moran_by_municipality(grids, geometry)
        target = output / "global_moran.parquet"
        moran.to_parquet(target, index=False)
        outputs["global_moran"] = str(target)

    report = {"outputs": outputs, "grid_rows": int(len(grids)), "ageb_rows": int(len(agebs))}
    (p.reports / "spatial_eda.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
