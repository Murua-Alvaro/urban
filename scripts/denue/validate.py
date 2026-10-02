from __future__ import annotations

import argparse
import json
from pathlib import Path

from urban_denue.config import ensure_dirs, paths
from urban_denue.validation import validate_extracted


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate extracted historical DENUE data")
    parser.add_argument("--root", default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    p = paths(args.root)
    ensure_dirs(p)
    report = validate_extracted(p.extracted)
    destination = args.report or p.reports / "validation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if not report.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
