from __future__ import annotations

import argparse
import json

from urban_denue.archive import acquire_archive, safe_extract, verify_archive
from urban_denue.catalog import edition_assets, municipality_catalog
from urban_denue.config import ensure_dirs, paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire, verify, extract and catalog DENUE historical data")
    parser.add_argument("--root", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    p = paths(args.root)
    ensure_dirs(p)
    archive = acquire_archive(p.archive, url=args.url, force=args.force) if args.url else acquire_archive(p.archive, force=args.force)
    verify_archive(archive)
    safe_extract(archive, p.extracted, force=args.force)
    summary = {
        "archive": str(archive),
        "extracted": str(p.extracted),
        "municipalities": len(municipality_catalog(p.extracted)),
        "editions": [a.source_edition for a in edition_assets(p.extracted)],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
