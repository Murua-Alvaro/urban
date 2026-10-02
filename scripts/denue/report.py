from __future__ import annotations

import argparse
import json

from urban_denue.config import ensure_dirs, paths
from urban_denue.reporting import municipality_report, state_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate human-readable DENUE EDA reports")
    parser.add_argument("--root", default=None)
    parser.add_argument("--municipality", default="012", help="INEGI municipality code, default Mazatlan 012")
    args = parser.parse_args()
    p = paths(args.root)
    ensure_dirs(p)
    state = state_report(p.processed, p.reports)
    municipal = municipality_report(p.processed, p.reports, args.municipality.zfill(3))
    result = {"state_report": str(state), "municipality_report": str(municipal)}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
