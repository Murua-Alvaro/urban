from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from panel import iter_editions


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical Parquet partitions from extracted historical DENUE JSON files.")
    parser.add_argument("--input", type=Path, default=Path("var/denue/extracted"))
    parser.add_argument("--output", type=Path, default=Path("var/denue/processed"))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    editions_dir = args.output / "editions"
    editions_dir.mkdir(parents=True, exist_ok=True)
    inventory: list[dict] = []

    for edition in iter_editions(args.input):
        out = editions_dir / f"denue_{edition.source_edition}.parquet"
        if out.exists() and not args.overwrite:
            frame = pd.read_parquet(out, columns=["establishments", "municipality_code"])
            inventory.append(
                {
                    "source_edition": edition.source_edition,
                    "edition_date": edition.edition_date.date().isoformat(),
                    "rows": int(len(frame)),
                    "establishments": int(frame["establishments"].sum()),
                    "municipalities": int(frame["municipality_code"].nunique()),
                    "path": str(out),
                    "cached": True,
                }
            )
            print(f"cached {edition.source_edition}: {out}")
            continue

        frame = edition.frame
        frame.to_parquet(out, index=False, compression="zstd")
        inventory.append(
            {
                "source_edition": edition.source_edition,
                "edition_date": edition.edition_date.date().isoformat(),
                "rows": int(len(frame)),
                "establishments": int(frame["establishments"].sum()),
                "municipalities": int(frame["municipality_code"].nunique()),
                "path": str(out),
                "cached": False,
            }
        )
        print(f"built {edition.source_edition}: {len(frame):,} rows / {frame['establishments'].sum():,} establishments")

    inventory_df = pd.DataFrame(inventory).sort_values("edition_date")
    inventory_df.to_csv(args.output / "inventory.csv", index=False)
    (args.output / "inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nInventory: {args.output / 'inventory.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
