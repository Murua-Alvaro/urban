from __future__ import annotations

import argparse
import json

from urban_denue.pipeline import STAGES, run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the reproducible historical DENUE pipeline")
    parser.add_argument("--root", default=None)
    parser.add_argument("--through", choices=STAGES + ["all"], default="all")
    parser.add_argument("--skip-moran", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()
    manifest = run_pipeline(args.root, through=args.through, skip_moran=args.skip_moran, force_download=args.force_download)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
