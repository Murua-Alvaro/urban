from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_EDITIONS = {
    "2010", "2011", "2012", "2013-A", "2013-B", "2015-02", "2016-01", "2016-10",
    "2017-03", "2017-11", "2018-03", "2018-11", "2019-04", "2019-11", "2020-04",
    "2020-11", "2021-05", "2021-11", "2022-05", "2022-11", "2023-11", "2024-05",
    "2024-11", "2025-05", "2026-05",
}
EXPECTED_FIELDS = ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"]
SMOKE_TOTALS = {
    ("2010", None): 94_961,
    ("2015-02", None): 107_458,
    ("2024-11", None): 135_239,
    ("2026-05", None): 138_882,
    ("2026-05", "25_012"): 27_487,
}
EXPECTED_ACCUMULATED_ESTABLISHMENTS = 2_889_999
EXPECTED_AGGREGATED_ROWS = 2_083_926


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the audited historical DENUE extraction before analysis.")
    parser.add_argument("--root", type=Path, default=Path("var/denue/extracted"))
    parser.add_argument("--report", type=Path, default=Path("var/denue/validation_report.json"))
    args = parser.parse_args()

    data = args.root / "data"
    core = json.loads((data / "core.json").read_text(encoding="utf-8"))
    edition_dir = data / "ediciones"
    files = {p.stem: p for p in edition_dir.glob("*.json")}
    errors: list[str] = []
    warnings: list[str] = []

    if set(files) != EXPECTED_EDITIONS:
        errors.append(f"Edition set mismatch: got {sorted(files)}, expected {sorted(EXPECTED_EDITIONS)}")

    accumulated_establishments = 0
    aggregated_rows = 0
    totals: dict[str, int] = {}
    municipality_totals: dict[tuple[str, str], int] = {}
    missing_ageb = missing_grid = missing_cp = 0

    for edition in sorted(EXPECTED_EDITIONS):
        if edition not in files:
            continue
        payload = json.loads(files[edition].read_text(encoding="utf-8"))
        edition_total = 0
        for municipality_code, municipality in payload.items():
            fields = municipality.get("fields")
            rows = municipality.get("rows", [])
            declared = int(municipality.get("total", 0))
            if fields != EXPECTED_FIELDS:
                errors.append(f"{edition}/{municipality_code}: schema {fields}")
                continue
            row_total = 0
            for row in rows:
                if len(row) != len(EXPECTED_FIELDS):
                    errors.append(f"{edition}/{municipality_code}: malformed row length={len(row)}")
                    continue
                n = int(row[7])
                if n <= 0:
                    errors.append(f"{edition}/{municipality_code}: non-positive n={n}")
                row_total += n
                aggregated_rows += 1
                missing_ageb += n if row[0] == "SIN_AGEB" else 0
                missing_grid += n if row[1] == "SIN_GRID" else 0
                missing_cp += n if row[5] == "SIN_CP" else 0
            if row_total != declared:
                errors.append(f"{edition}/{municipality_code}: rows={row_total}, declared={declared}")
            edition_total += declared
            municipality_totals[(edition, municipality_code)] = declared
        totals[edition] = edition_total
        accumulated_establishments += edition_total

    state_totals = core.get("stateTotals", {})
    for edition, total in totals.items():
        core_total = int(state_totals.get(edition, -1))
        if total != core_total:
            errors.append(f"{edition}: edition total={total}, core.stateTotals={core_total}")

    for (edition, municipality_code), expected in SMOKE_TOTALS.items():
        actual = totals.get(edition) if municipality_code is None else municipality_totals.get((edition, municipality_code))
        if actual != expected:
            errors.append(f"Smoke total mismatch {edition}/{municipality_code or 'STATE'}: {actual} != {expected}")

    if accumulated_establishments != EXPECTED_ACCUMULATED_ESTABLISHMENTS:
        errors.append(
            f"Accumulated establishment count {accumulated_establishments} != {EXPECTED_ACCUMULATED_ESTABLISHMENTS}"
        )
    if aggregated_rows != EXPECTED_AGGREGATED_ROWS:
        errors.append(f"Aggregated row count {aggregated_rows} != {EXPECTED_AGGREGATED_ROWS}")

    grids = json.loads((data / "cuadriculas.json").read_text(encoding="utf-8"))
    grid_feature_count = 0
    for municipality_code, collection in grids.items():
        features = collection.get("features", [])
        grid_feature_count += len(features)
        ids = [feature.get("properties", {}).get("grid") for feature in features]
        if len(ids) != len(set(ids)):
            errors.append(f"Duplicate grid id inside municipality geometry: {municipality_code}")
    if grid_feature_count != 2_912:
        warnings.append(f"Grid feature count changed from audited value 2,912 to {grid_feature_count}")

    report = {
        "ok": not errors,
        "editions": len(files),
        "aggregated_rows": aggregated_rows,
        "accumulated_establishments": accumulated_establishments,
        "grid_features": grid_feature_count,
        "missing_weighted": {"ageb": missing_ageb, "grid": missing_grid, "postal_code": missing_cp},
        "smoke_totals": {f"{e}:{m or 'STATE'}": (totals.get(e) if m is None else municipality_totals.get((e, m))) for (e, m) in SMOKE_TOTALS},
        "errors": errors,
        "warnings": warnings,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
