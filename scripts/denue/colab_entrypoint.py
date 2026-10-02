from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

VALID_STAGES = ("load", "validate", "clean", "eda", "spatial", "features", "all")


def run(stage: str, root: Path, skip_moran: bool = True) -> int:
    if stage not in VALID_STAGES:
        raise ValueError(f"Unknown stage: {stage}")

    cmd = [
        sys.executable,
        "scripts/denue/run_pipeline.py",
        "--root",
        str(root),
        "--through",
        stage,
    ]
    if skip_moran and stage in {"spatial", "features", "all"}:
        cmd.append("--skip-moran")

    env = os.environ.copy()
    env["DENUE_ROOT"] = str(root)
    print("Running:", " ".join(cmd), flush=True)
    return subprocess.call(cmd, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Colab-friendly entrypoint for the reproducible DENUE pipeline."
    )
    parser.add_argument("--stage", choices=VALID_STAGES, default="eda")
    parser.add_argument("--root", type=Path, default=Path("/content/urban-denue"))
    parser.add_argument("--with-moran", action="store_true")
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    return run(args.stage, args.root, skip_moran=not args.with_moran)


if __name__ == "__main__":
    raise SystemExit(main())
