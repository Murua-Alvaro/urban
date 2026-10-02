from __future__ import annotations

import argparse
import json

from urban_denue.config import ensure_dirs, paths
from urban_denue.eda import build_eda, load_staged, write_eda


def main() -> int:
    parser = argparse.ArgumentParser(description="Build core historical DENUE EDA artifacts")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    p = paths(args.root)
    ensure_dirs(p)
    frame = load_staged(p.staged)
    artifacts = build_eda(frame)
    outputs = write_eda(artifacts, p.processed / "eda_core")
    summary = {
        "rows_staged": int(len(frame)),
        "establishments_weighted": int(frame["establishments"].sum()),
        "outputs": {k: str(v) for k, v in outputs.items()},
    }
    (p.reports / "eda_core.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
