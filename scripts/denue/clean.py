from __future__ import annotations

import argparse
import json

from urban_denue.catalog import edition_assets
from urban_denue.cleaning import clean_asset, write_clean_partition
from urban_denue.config import ensure_dirs, paths
from urban_denue.validation import validate_extracted


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and build canonical DENUE parquet partitions")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    p = paths(args.root)
    ensure_dirs(p)
    validation = validate_extracted(p.extracted)
    if validation.errors:
        raise SystemExit("validation failed; cleaning aborted")

    outputs = []
    for asset in edition_assets(p.extracted):
        result = clean_asset(p.extracted, asset)
        outputs.append(str(write_clean_partition(result, p.staged)))
    (p.reports / "cleaning.json").write_text(json.dumps({"partitions": outputs}, indent=2), encoding="utf-8")
    print(f"wrote {len(outputs)} clean partitions to {p.staged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
