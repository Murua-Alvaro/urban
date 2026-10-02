from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from urban_denue.config import paths
from urban_denue.modeling import run_models, write_models
from urban_denue.pipeline import run_pipeline

PIPELINE_STAGES = ("load", "validate", "clean", "eda", "spatial", "features")
VALID_STAGES = PIPELINE_STAGES + ("model", "all")


def run(stage: str, root: Path, skip_moran: bool = True) -> int:
    if stage not in VALID_STAGES:
        raise ValueError(f"Unknown stage: {stage}")

    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    pipeline_stage = "all" if stage in {"model", "all"} else stage
    manifest = run_pipeline(
        root=root,
        through=pipeline_stage,
        skip_moran=skip_moran,
        force_download=False,
    )

    result: dict[str, object] = {
        "root": str(root),
        "stage": stage,
        "pipeline": manifest,
    }

    if stage in {"model", "all"}:
        p = paths(root)
        features_path = p.processed / "feature_store" / "grid_features.parquet"
        if not features_path.exists():
            raise FileNotFoundError(
                f"missing feature store required for modeling: {features_path}"
            )
        features = pd.read_parquet(features_path)
        artifacts = run_models(features)
        outputs = write_models(
            artifacts,
            p.processed / "models" / "grid_dynamics",
        )
        result["models"] = {
            "outputs": outputs,
            "diagnostics": artifacts.diagnostics,
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Colab-friendly direct entrypoint for the reproducible DENUE pipeline."
    )
    parser.add_argument("--stage", choices=VALID_STAGES, default="eda")
    parser.add_argument("--root", type=Path, default=Path("/content/urban-denue"))
    parser.add_argument("--with-moran", action="store_true")
    args = parser.parse_args()
    return run(args.stage, args.root, skip_moran=not args.with_moran)


if __name__ == "__main__":
    raise SystemExit(main())
