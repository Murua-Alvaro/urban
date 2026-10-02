from __future__ import annotations

import argparse
import json
import pandas as pd

from urban_denue.config import ensure_dirs, paths
from urban_denue.modeling import run_models, write_models


def main() -> int:
    parser = argparse.ArgumentParser(description="Run exploratory/predictive DENUE grid models")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    p = paths(args.root)
    ensure_dirs(p)
    features = pd.read_parquet(p.processed / "feature_store" / "grid_features.parquet")
    artifacts = run_models(features)
    outputs = write_models(artifacts, p.processed / "models" / "grid_dynamics")
    print(json.dumps({"outputs": outputs, "diagnostics": artifacts.diagnostics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
