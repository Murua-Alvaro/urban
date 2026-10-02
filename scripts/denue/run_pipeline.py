from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(*args: str) -> None:
    print("\n$", " ".join(args), flush=True)
    subprocess.run(args, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the audited DENUE pipeline end-to-end.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--overwrite-panel", action="store_true")
    parser.add_argument("--skip-models", action="store_true")
    args = parser.parse_args()

    py = args.python
    fetch = [py, "scripts/denue/fetch_archive.py", "--extract"]
    if args.force_download:
        fetch.append("--force")
    run(*fetch)
    run(py, "scripts/denue/validate_dataset.py")

    build = [py, "scripts/denue/build_panel.py"]
    if args.overwrite_panel:
        build.append("--overwrite")
    run(*build)
    run(py, "scripts/denue/run_eda.py")
    run(py, "scripts/denue/territorial_features.py", "--level", "grid")
    run(py, "scripts/denue/territorial_features.py", "--level", "ageb")
    if not args.skip_models:
        run(py, "scripts/denue/model_grid_dynamics.py")

    print("\nDENUE pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
