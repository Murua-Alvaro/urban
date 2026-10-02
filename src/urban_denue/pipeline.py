from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from .archive import acquire_archive, safe_extract, verify_archive
from .catalog import edition_assets
from .cleaning import clean_asset, write_clean_partition
from .config import ensure_dirs, paths
from .constants import ARCHIVE_SHA256
from .eda import build_eda, load_staged, write_eda
from .features import build_model_features, geography_sector_lq, queen_neighbor_features, write_feature_store
from .spatial_eda import (
    add_grid_area,
    ageb_panel,
    geography_diversity,
    global_moran_by_municipality,
    grid_panel,
    load_grid_geometry,
    polycentricity_summary,
)
from .validation import validate_extracted

STAGES = ["load", "validate", "clean", "eda", "spatial", "features"]


def environment_snapshot() -> dict:
    packages = {}
    for name in ["pandas", "numpy", "pyarrow", "geopandas", "shapely", "libpysal", "esda", "statsmodels"]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
    }


def _requested(through: str) -> list[str]:
    if through == "all":
        return STAGES.copy()
    if through not in STAGES:
        raise ValueError(f"unknown pipeline stage: {through}")
    return STAGES[: STAGES.index(through) + 1]


def run_pipeline(root: str | Path | None = None, through: str = "all", skip_moran: bool = False, force_download: bool = False) -> dict:
    p = paths(root)
    ensure_dirs(p)
    stages = _requested(through)
    manifest = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": ARCHIVE_SHA256,
        "requested_through": through,
        "skip_moran": skip_moran,
        "environment": environment_snapshot(),
        "stages": {},
    }

    if "load" in stages:
        archive = acquire_archive(p.archive, force=force_download)
        verify_archive(archive)
        safe_extract(archive, p.extracted)
        manifest["stages"]["load"] = {"archive": str(archive), "extracted": str(p.extracted)}

    if "validate" in stages:
        report = validate_extracted(p.extracted)
        report_path = p.reports / "validation.json"
        report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["stages"]["validate"] = {"report": str(report_path), "valid": not report.errors, "errors": len(report.errors)}
        if report.errors:
            raise RuntimeError(f"DENUE validation failed with {len(report.errors)} errors")

    if "clean" in stages:
        outputs = []
        for asset in edition_assets(p.extracted):
            outputs.append(str(write_clean_partition(clean_asset(p.extracted, asset), p.staged)))
        manifest["stages"]["clean"] = {"partitions": len(outputs), "staged_root": str(p.staged)}

    frame = None
    if any(stage in stages for stage in ["eda", "spatial", "features"]):
        frame = load_staged(p.staged)

    if "eda" in stages:
        artifacts = build_eda(frame)
        outputs = write_eda(artifacts, p.processed / "eda_core")
        manifest["stages"]["eda"] = {
            "rows_staged": int(len(frame)),
            "establishments_weighted": int(frame["establishments"].sum()),
            "outputs": {k: str(v) for k, v in outputs.items()},
        }

    grids = agebs = grid_div = ageb_div = geometry = None
    if any(stage in stages for stage in ["spatial", "features"]):
        grids = grid_panel(frame)
        agebs = ageb_panel(frame)
        grid_div = geography_diversity(frame, "grid_analysis")
        ageb_div = geography_diversity(frame, "ageb_analysis")
        geometry = add_grid_area(load_grid_geometry(p.extracted))

    if "spatial" in stages:
        outdir = p.processed / "spatial_eda"
        outdir.mkdir(parents=True, exist_ok=True)
        poly = polycentricity_summary(grids)
        outputs = {}
        for name, data in {
            "grid_panel": grids,
            "ageb_panel": agebs,
            "grid_diversity": grid_div,
            "ageb_diversity": ageb_div,
            "polycentricity": poly,
        }.items():
            target = outdir / f"{name}.parquet"
            data.to_parquet(target, index=False)
            outputs[name] = str(target)
        geom_target = outdir / "grid_geometry.parquet"
        geometry.to_parquet(geom_target, index=False)
        outputs["grid_geometry"] = str(geom_target)
        if not skip_moran:
            moran = global_moran_by_municipality(grids, geometry)
            moran_target = outdir / "global_moran.parquet"
            moran.to_parquet(moran_target, index=False)
            outputs["global_moran"] = str(moran_target)
        manifest["stages"]["spatial"] = {"outputs": outputs, "grid_rows": int(len(grids)), "ageb_rows": int(len(agebs))}

    if "features" in stages:
        grid_features = build_model_features(frame, grids, grid_div, "grid_analysis")
        grid_features = queen_neighbor_features(grid_features, geometry)
        ageb_features = build_model_features(frame, agebs, ageb_div, "ageb_analysis")
        outputs = write_feature_store({
            "grid_features": grid_features,
            "ageb_features": ageb_features,
            "grid_sector_lq": geography_sector_lq(frame, "grid_analysis"),
            "ageb_sector_lq": geography_sector_lq(frame, "ageb_analysis"),
        }, p.processed / "feature_store")
        manifest["stages"]["features"] = {
            "outputs": outputs,
            "grid_feature_rows": int(len(grid_features)),
            "ageb_feature_rows": int(len(ageb_features)),
            "grid_model_transitions": int(grid_features["model_transition_ok"].sum()),
            "ageb_model_transitions": int(ageb_features["model_transition_ok"].sum()),
        }

    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    run_manifest = p.reports / "pipeline_manifest.json"
    run_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
