from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

EXPECTED_FIELDS = ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"]

# Canonical dates used for longitudinal work. Source labels are preserved separately.
EDITION_DATES = {
    "2010": "2010-07-01",
    "2011": "2011-03-01",
    "2012": "2012-06-01",
    "2013-A": "2013-07-01",
    "2013-B": "2013-10-01",
    "2015-02": "2015-01-01",  # official DENUE 01/2015; source filename label was retained upstream
    "2016-01": "2016-01-01",
    "2016-10": "2016-10-01",
    "2017-03": "2017-03-01",
    "2017-11": "2017-11-01",
    "2018-03": "2018-03-01",
    "2018-11": "2018-11-01",
    "2019-04": "2019-04-01",
    "2019-11": "2019-11-01",
    "2020-04": "2020-04-01",
    "2020-11": "2020-11-01",
    "2021-05": "2021-05-01",
    "2021-11": "2021-11-01",
    "2022-05": "2022-05-01",
    "2022-11": "2022-11-01",
    "2023-11": "2023-11-01",
    "2024-05": "2024-05-01",
    "2024-11": "2024-11-01",
    "2025-05": "2025-05-01",
    "2026-05": "2026-05-01",
}

REBENCHMARK_EDITIONS = {"2015-02", "2019-11", "2024-11"}


@dataclass(frozen=True)
class EditionFrame:
    source_edition: str
    edition_date: pd.Timestamp
    frame: pd.DataFrame


def extracted_data_root(extracted_root: Path) -> Path:
    root = extracted_root / "data"
    if not (root / "core.json").exists():
        raise FileNotFoundError(f"DENUE core.json not found under {root}")
    return root


def load_core(extracted_root: Path) -> dict:
    root = extracted_data_root(extracted_root)
    return json.loads((root / "core.json").read_text(encoding="utf-8"))


def municipality_catalog(extracted_root: Path) -> dict[str, dict]:
    core = load_core(extracted_root)
    return core["manifest"]["municipalities"]


def edition_files(extracted_root: Path) -> list[Path]:
    root = extracted_data_root(extracted_root) / "ediciones"
    files = [p for p in root.glob("*.json") if p.stem in EDITION_DATES]
    return sorted(files, key=lambda p: pd.Timestamp(EDITION_DATES[p.stem]))


def _weighted_bool(flags: pd.Series, bit: int) -> pd.Series:
    return flags.fillna(0).astype("int16").map(lambda value: bool(value & bit))


def municipality_payload_to_frame(
    source_edition: str,
    municipality_code: str,
    payload: dict,
    municipality_meta: dict,
) -> pd.DataFrame:
    fields = payload.get("fields")
    if fields != EXPECTED_FIELDS:
        raise ValueError(
            f"Unexpected schema for {source_edition}/{municipality_code}: {fields}; expected {EXPECTED_FIELDS}"
        )

    df = pd.DataFrame(payload.get("rows", []), columns=fields)
    if df.empty:
        df = pd.DataFrame(columns=EXPECTED_FIELDS)

    df = df.rename(
        columns={
            "size": "size_band",
            "class": "scian6",
            "cp": "postal_code",
            "n": "establishments",
        }
    )
    df["source_edition"] = source_edition
    df["edition_date"] = pd.Timestamp(EDITION_DATES[source_edition])
    df["rebenchmark"] = source_edition in REBENCHMARK_EDITIONS
    df["state_code"] = municipality_meta.get("state_code", "25")
    df["state_name"] = municipality_meta.get("state", "Sinaloa")
    df["municipality_code"] = municipality_code
    df["municipality_inegi"] = municipality_meta.get("mun_code")
    df["municipality_name"] = municipality_meta.get("name")

    for col in ["ageb", "grid", "sector", "scian6", "postal_code"]:
        df[col] = df[col].astype("string")
    df["size_band"] = pd.to_numeric(df["size_band"], errors="coerce").astype("Int16")
    df["flags"] = pd.to_numeric(df["flags"], errors="coerce").fillna(0).astype("int16")
    df["establishments"] = pd.to_numeric(df["establishments"], errors="coerce").fillna(0).astype("int32")

    df["has_phone"] = _weighted_bool(df["flags"], 1)
    df["has_email"] = _weighted_bool(df["flags"], 2)
    df["has_web"] = _weighted_bool(df["flags"], 4)

    df["missing_ageb"] = df["ageb"].isna() | df["ageb"].eq("SIN_AGEB")
    df["missing_grid"] = df["grid"].isna() | df["grid"].eq("SIN_GRID")
    df["missing_postal_code"] = df["postal_code"].isna() | df["postal_code"].eq("SIN_CP")
    df["postal_format_valid"] = df["postal_code"].fillna("").str.fullmatch(r"\d{5}")
    # Heuristic only. Kept separate from format validity so it is never mistaken for official CP validation.
    df["postal_prefix_plausible_sinaloa"] = df["postal_code"].fillna("").str.match(r"^(80|81|82)\d{3}$")

    expected_total = int(payload.get("total", 0))
    observed_total = int(df["establishments"].sum())
    if observed_total != expected_total:
        raise ValueError(
            f"Total mismatch for {source_edition}/{municipality_code}: rows={observed_total}, declared={expected_total}"
        )
    return df


def load_edition(extracted_root: Path, source_edition: str) -> EditionFrame:
    if source_edition not in EDITION_DATES:
        raise KeyError(f"Unknown DENUE edition: {source_edition}")
    root = extracted_data_root(extracted_root)
    path = root / "ediciones" / f"{source_edition}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    catalog = municipality_catalog(extracted_root)

    frames: list[pd.DataFrame] = []
    for municipality_code, municipality_payload in payload.items():
        if municipality_code not in catalog:
            raise KeyError(f"Municipality {municipality_code} missing from core catalog")
        frames.append(
            municipality_payload_to_frame(
                source_edition,
                municipality_code,
                municipality_payload,
                catalog[municipality_code],
            )
        )
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return EditionFrame(source_edition, pd.Timestamp(EDITION_DATES[source_edition]), frame)


def iter_editions(extracted_root: Path) -> Iterator[EditionFrame]:
    for path in edition_files(extracted_root):
        yield load_edition(extracted_root, path.stem)


def weighted_share(frame: pd.DataFrame, mask: pd.Series) -> float:
    total = frame["establishments"].sum()
    if total <= 0:
        return float("nan")
    return float(frame.loc[mask, "establishments"].sum() / total)


def concentration_metrics(frame: pd.DataFrame, key: str = "sector") -> dict[str, float]:
    counts = frame.groupby(key, dropna=False)["establishments"].sum().astype(float)
    total = counts.sum()
    if total <= 0:
        return {"hhi": float("nan"), "shannon": float("nan"), "effective_categories": float("nan")}
    shares = counts / total
    hhi = float(np.square(shares).sum())
    positive = shares[shares > 0]
    shannon = float(-(positive * np.log(positive)).sum())
    return {"hhi": hhi, "shannon": shannon, "effective_categories": float(np.exp(shannon))}
