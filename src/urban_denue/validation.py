from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .catalog import edition_assets, load_edition_payload, municipality_catalog
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


def _warn(report: ValidationReport, edition: str, municipality: str | None, code: str, message: str) -> None:
    report.issues.append(ValidationIssue("warning", edition, municipality, code, message))


def _error(report: ValidationReport, edition: str, municipality: str | None, code: str, message: str) -> None:
    report.issues.append(ValidationIssue("error", edition, municipality, code, message))


def validate_extracted(extracted_root: Path) -> ValidationReport:
    catalog = municipality_catalog(extracted_root)
    report = ValidationReport(municipalities=len(catalog))
    assets = edition_assets(extracted_root)
    report.editions = len(assets)
    seen_editions: set[str] = set()

    for asset in assets:
        if asset.source_edition in seen_editions:
            _error(report, asset.source_edition, None, "duplicate_edition", "edition label appears more than once")
        seen_editions.add(asset.source_edition)
        payload = load_edition_payload(asset)
        for municipality_code, block in payload.items():
            if municipality_code not in catalog:
                _error(report, asset.source_edition, municipality_code, "unknown_municipality", "municipality is absent from core catalog")
                continue
            fields = block.get("fields")
            if fields != EXPECTED_FIELDS:
                _error(report, asset.source_edition, municipality_code, "schema", f"fields={fields!r}")
                continue
            rows = block.get("rows", [])
            if not isinstance(rows, list):
                _error(report, asset.source_edition, municipality_code, "rows_type", "rows must be a list")
                continue

            declared_total = int(block.get("total", 0))
            observed_total = 0
            seen_keys: set[tuple[Any, ...]] = set()
            for idx, row in enumerate(rows):
                report.rows += 1
                if not isinstance(row, list) or len(row) != len(EXPECTED_FIELDS):
                    _error(report, asset.source_edition, municipality_code, "row_width", f"row {idx} has invalid width")
                    continue
                key = tuple(row[:-1])
                if key in seen_keys:
                    _error(report, asset.source_edition, municipality_code, "duplicate_group", f"duplicate grouped key at row {idx}")
                seen_keys.add(key)
                ageb, grid, sector, size_band, scian6, postal_code, flags, n = row
                try:
                    n_int = int(n)
                    if n_int < 0 or n_int != n:
                        raise ValueError
                except (TypeError, ValueError):
                    _error(report, asset.source_edition, municipality_code, "invalid_n", f"row {idx}: {n!r}")
                    continue
                observed_total += n_int
                if ageb in (None, "", "SIN_AGEB"):
                    report.missing_ageb += n_int
                if grid in (None, "", "SIN_GRID"):
                    report.missing_grid += n_int
                if postal_code in (None, "", "SIN_CP"):
                    report.missing_postal_code += n_int
                elif not (isinstance(postal_code, str) and len(postal_code) == 5 and postal_code.isdigit()):
                    report.suspicious_postal_code += n_int
                elif not postal_code.startswith(("80", "81", "82")):
                    report.suspicious_postal_code += n_int
                if not (isinstance(str(sector), str) and str(sector).isdigit() and len(str(sector)) == 2):
                    _warn(report, asset.source_edition, municipality_code, "sector_format", f"row {idx}: {sector!r}")
                if not (str(scian6).isdigit() and len(str(scian6)) == 6):
                    _warn(report, asset.source_edition, municipality_code, "scian6_format", f"row {idx}: {scian6!r}")
                try:
                    flag_int = int(flags)
                    if flag_int < 0 or flag_int > 7:
                        raise ValueError
                except (TypeError, ValueError):
                    _warn(report, asset.source_edition, municipality_code, "flags_range", f"row {idx}: {flags!r}")

            report.establishments += observed_total
            if observed_total != declared_total:
                _error(report, asset.source_edition, municipality_code, "total_mismatch", f"rows={observed_total}, declared={declared_total}")

    if not assets:
        _error(report, "", None, "no_editions", "no edition JSON files found")
    return report
