from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .catalog import data_root, edition_assets, load_core, load_edition_payload, municipality_catalog
from .constants import EXPECTED_FIELDS


@dataclass
class ValidationIssue:
    severity: str
    edition: str
    municipality: str | None
    code: str
    message: str


@dataclass
class ValidationReport:
    editions: int = 0
    municipalities: int = 0
    rows: int = 0
    establishments: int = 0
    missing_ageb: int = 0
    missing_grid: int = 0
    missing_postal_code: int = 0
    suspicious_postal_code: int = 0
    core_total_checks: int = 0
    territorial_checks: int = 0
    activity_catalog_checks: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["error_count"] = len(self.errors)
        payload["warning_count"] = len(self.issues) - len(self.errors)
        payload["valid"] = not self.errors
        return payload


def _issue(report: ValidationReport, severity: str, edition: str, municipality: str | None, code: str, message: str) -> None:
    report.issues.append(ValidationIssue(severity, edition, municipality, code, message))


def _warn(report: ValidationReport, edition: str, municipality: str | None, code: str, message: str) -> None:
    _issue(report, "warning", edition, municipality, code, message)


def _error(report: ValidationReport, edition: str, municipality: str | None, code: str, message: str) -> None:
    _issue(report, "error", edition, municipality, code, message)


def validate_extracted(extracted_root: Path) -> ValidationReport:
    core = load_core(extracted_root)
    catalog = municipality_catalog(extracted_root)
    activity_catalog = core.get("activities", {})
    state_totals_reference = core.get("stateTotals", {})
    summaries = core.get("summaries", {})
    report = ValidationReport(municipalities=len(catalog))
    assets = edition_assets(extracted_root)
    report.editions = len(assets)
    if len(assets) != 25:
        _error(report, "", None, "edition_count", f"expected 25 editions, found {len(assets)}")

    totals_by_key: dict[tuple[str, str], int] = {}
    missing_ageb_by_key: dict[tuple[str, str], int] = {}
    missing_grid_by_key: dict[tuple[str, str], int] = {}
    state_totals_observed: dict[str, int] = {}
    seen_editions: set[str] = set()

    for asset in assets:
        edition = asset.source_edition
        if edition in seen_editions:
            _error(report, edition, None, "duplicate_edition", "edition label appears more than once")
        seen_editions.add(edition)
        payload = load_edition_payload(asset)
        state_total = 0

        for municipality_code, block in payload.items():
            if municipality_code not in catalog:
                _error(report, edition, municipality_code, "unknown_municipality", "municipality is absent from core catalog")
                continue
            if block.get("fields") != EXPECTED_FIELDS:
                _error(report, edition, municipality_code, "schema", f"fields={block.get('fields')!r}")
                continue
            rows = block.get("rows", [])
            if not isinstance(rows, list):
                _error(report, edition, municipality_code, "rows_type", "rows must be a list")
                continue

            observed_total = 0
            missing_ageb_local = 0
            missing_grid_local = 0
            seen_keys: set[tuple[Any, ...]] = set()
            for idx, row in enumerate(rows):
                report.rows += 1
                if not isinstance(row, list) or len(row) != len(EXPECTED_FIELDS):
                    _error(report, edition, municipality_code, "row_width", f"row {idx} has invalid width")
                    continue
                key = tuple(row[:-1])
                if key in seen_keys:
                    _error(report, edition, municipality_code, "duplicate_group", f"duplicate grouped key at row {idx}")
                seen_keys.add(key)

                ageb, grid, sector, size_band, scian6, postal_code, flags, n = row
                try:
                    n_int = int(n)
                    if n_int < 0 or float(n_int) != float(n):
                        raise ValueError
                except (TypeError, ValueError):
                    _error(report, edition, municipality_code, "invalid_n", f"row {idx}: {n!r}")
                    continue
                observed_total += n_int

                if ageb in (None, "", "SIN_AGEB"):
                    report.missing_ageb += n_int
                    missing_ageb_local += n_int
                if grid in (None, "", "SIN_GRID"):
                    report.missing_grid += n_int
                    missing_grid_local += n_int
                if postal_code in (None, "", "SIN_CP"):
                    report.missing_postal_code += n_int
                elif not (isinstance(postal_code, str) and len(postal_code) == 5 and postal_code.isdigit()):
                    report.suspicious_postal_code += n_int
                elif not postal_code.startswith(("80", "81", "82")):
                    report.suspicious_postal_code += n_int

                if not (str(sector).isdigit() and len(str(sector)) == 2):
                    _warn(report, edition, municipality_code, "sector_format", f"row {idx}: {sector!r}")
                scian_text = str(scian6)
                if not (scian_text.isdigit() and len(scian_text) == 6):
                    _warn(report, edition, municipality_code, "scian6_format", f"row {idx}: {scian6!r}")
                elif activity_catalog:
                    report.activity_catalog_checks += 1
                    if scian_text not in activity_catalog:
                        _warn(report, edition, municipality_code, "scian6_not_in_activity_catalog", scian_text)
                try:
                    flag_int = int(flags)
                    if flag_int < 0 or flag_int > 7:
                        raise ValueError
                except (TypeError, ValueError):
                    _warn(report, edition, municipality_code, "flags_range", f"row {idx}: {flags!r}")

            declared_total = int(block.get("total", 0))
            if observed_total != declared_total:
                _error(report, edition, municipality_code, "total_mismatch", f"rows={observed_total}, declared={declared_total}")

            totals_by_key[(edition, municipality_code)] = observed_total
            missing_ageb_by_key[(edition, municipality_code)] = missing_ageb_local
            missing_grid_by_key[(edition, municipality_code)] = missing_grid_local
            state_total += observed_total
            report.establishments += observed_total

            history_ref = catalog[municipality_code].get("history_totals", {}).get(edition)
            if history_ref is not None:
                report.core_total_checks += 1
                if observed_total != int(history_ref):
                    _error(report, edition, municipality_code, "core_history_total_mismatch", f"observed={observed_total}, core={history_ref}")
            summary_ref = summaries.get(municipality_code, {}).get("summary", {}).get(edition, {}).get("total")
            if summary_ref is not None:
                report.core_total_checks += 1
                if observed_total != int(summary_ref):
                    _error(report, edition, municipality_code, "core_summary_total_mismatch", f"observed={observed_total}, summary={summary_ref}")

        state_totals_observed[edition] = state_total
        if edition in state_totals_reference:
            report.core_total_checks += 1
            if state_total != int(state_totals_reference[edition]):
                _error(report, edition, None, "state_total_mismatch", f"observed={state_total}, core={state_totals_reference[edition]}")

    territorial_path = data_root(extracted_root) / "historico_territorial.json"
    if territorial_path.exists():
        territorial = json.loads(territorial_path.read_text(encoding="utf-8"))
        territorial_editions = territorial.get("editions", [])
        if territorial_editions != [a.source_edition for a in assets]:
            _error(report, "", None, "territorial_edition_order", "historico_territorial edition order differs from edition assets")
        index = {edition: i for i, edition in enumerate(territorial_editions)}
        for municipality_code, geo in territorial.get("municipalities", {}).items():
            for edition, i in index.items():
                key = (edition, municipality_code)
                if key not in totals_by_key:
                    continue
                ageb_sum = sum(int(values[i]) for values in geo.get("ageb", {}).values() if i < len(values))
                grid_sum = sum(int(values[i]) for values in geo.get("grid", {}).values() if i < len(values))
                expected_ageb = totals_by_key[key] - missing_ageb_by_key.get(key, 0)
                expected_grid = totals_by_key[key] - missing_grid_by_key.get(key, 0)
                report.territorial_checks += 2
                if ageb_sum != expected_ageb:
                    _error(report, edition, municipality_code, "territorial_ageb_mismatch", f"series={ageb_sum}, expected={expected_ageb}")
                if grid_sum != expected_grid:
                    _error(report, edition, municipality_code, "territorial_grid_mismatch", f"series={grid_sum}, expected={expected_grid}")
    else:
        _warn(report, "", None, "territorial_missing", "historico_territorial.json not found")

    if set(state_totals_observed) != set(state_totals_reference):
        _warn(report, "", None, "state_total_edition_set", "observed edition set differs from core stateTotals")
    return report
