from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PIPELINE_STAGES = ("load", "validate", "clean", "eda", "spatial", "features")
VALID_STAGES = PIPELINE_STAGES + ("model", "all")


def _run(cmd: list[str], env: dict[str, str]) -> None:
    print("Running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, env=env, check=True)


def run(stage: str, root: Path, skip_moran: bool = True) -> int:
    if stage not in VALID_STAGES:
        raise ValueError(f"Unknown stage: {stage}")

    env = os.environ.copy()
    env["DENUE_ROOT"] = str(root)

    if stage in PIPELINE_STAGES:
        cmd = [
            sys.executable,
            "scripts/denue/run_pipeline.py",
            "--root",
            str(root),
            "--through",
            stage,
        ]
        if skip_moran and stage in {"spatial", "features"}:
            cmd.append("--skip-moran")
        _run(cmd, env)
        return 0

    # Modeling requires the full feature store first.
    pipeline_cmd = [
        sys.executable,
        "scripts/denue/run_pipeline.py",
        "--root",
        str(root),
        "--through",
        "all",
    ]
    if skip_moran:
        pipeline_cmd.append("--skip-moran")
    _run(pipeline_cmd, env)

    model_cmd = [sys.executable, "scripts/denue/model.py", "--root", str(root)]
    _run(model_cmd, env)
    return 0


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
