from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import EditionAsset, load_edition_payload, municipality_catalog
from .constants import EXPECTED_FIELDS

EDITION_DATES = {
    "2010": "2010-07-01",
    "2011": "2011-03-01",
    "2012": "2012-06-01",
    "2013-A": "2013-07-01",
    "2013-B": "2013-10-01",
    "2015-02": "2015-01-01",
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

CANONICAL_EDITION = {
    "2010": "2010-07",
    "2011": "2011-03",
    "2012": "2012-06",
    "2013-A": "2013-07",
    "2013-B": "2013-10",
    "2015-02": "2015-01",
}
REBENCHMARK_EDITIONS = {"2015-02", "2019-11", "2024-11"}


@dataclass(frozen=True)
class CleanResult:
    edition: str
    canonical_edition: str
    frame: pd.DataFrame


def _contact_flag(flags: pd.Series, bit: int) -> pd.Series:
    values = pd.to_numeric(flags, errors="coerce").fillna(0).astype("int16")
    return values.map(lambda x: bool(int(x) & bit)).astype("boolean")


def _postal_status(series: pd.Series) -> pd.Series:
    s = series.astype("string")
    missing = s.isna() | s.eq("") | s.eq("SIN_CP")
    valid_format = s.fillna("").str.fullmatch(r"\d{5}")
    plausible = s.fillna("").str.match(r"^(80|81|82)\d{3}$")
    status = pd.Series("valid_plausible", index=s.index, dtype="string")
    status.loc[missing] = "missing"
    status.loc[~missing & ~valid_format] = "invalid_format"
    status.loc[~missing & valid_format & ~plausible] = "valid_format_outside_expected_sinaloa_range"
    return status


def clean_asset(extracted_root: Path, asset: EditionAsset) -> CleanResult:
    if asset.source_edition not in EDITION_DATES:
        raise KeyError(f"unmapped edition: {asset.source_edition}")
    catalog = municipality_catalog(extracted_root)
    payload = load_edition_payload(asset)
    frames: list[pd.DataFrame] = []

    for municipality_code, block in payload.items():
        if block.get("fields") != EXPECTED_FIELDS:
            raise ValueError(f"unexpected schema for {asset.source_edition}/{municipality_code}")
        df = pd.DataFrame(block.get("rows", []), columns=EXPECTED_FIELDS)
        if df.empty:
            continue
        meta = catalog[municipality_code]
        df = df.rename(columns={"size": "size_band", "class": "scian6", "cp": "postal_code", "n": "establishments"})
        df["source_edition"] = asset.source_edition
        df["canonical_edition"] = CANONICAL_EDITION.get(asset.source_edition, asset.source_edition)
        df["edition_date"] = pd.Timestamp(EDITION_DATES[asset.source_edition])
        df["rebenchmark"] = asset.source_edition in REBENCHMARK_EDITIONS
        df["state_code"] = "25"
        df["state_name"] = "Sinaloa"
        df["municipality_key"] = municipality_code
        df["municipality_code"] = str(meta.get("mun_code") or municipality_code.split("_")[-1]).zfill(3)
        df["municipality_name"] = meta.get("name")

        for col in ("ageb", "grid", "sector", "scian6", "postal_code"):
            df[col] = df[col].astype("string")
        df["sector"] = df["sector"].str.zfill(2)
        df["scian6"] = df["scian6"].str.zfill(6)
        df["size_band"] = pd.to_numeric(df["size_band"], errors="coerce").astype("Int16")
        df["flags"] = pd.to_numeric(df["flags"], errors="coerce").fillna(0).astype("Int16")
        df["establishments"] = pd.to_numeric(df["establishments"], errors="raise").astype("int32")

        df["has_phone"] = _contact_flag(df["flags"], 1)
        df["has_email"] = _contact_flag(df["flags"], 2)
        df["has_web"] = _contact_flag(df["flags"], 4)
        df["missing_ageb"] = df["ageb"].isna() | df["ageb"].isin(["", "SIN_AGEB"])
        df["missing_grid"] = df["grid"].isna() | df["grid"].isin(["", "SIN_GRID"])
        df["postal_status"] = _postal_status(df["postal_code"])
        df["ageb_analysis"] = df["ageb"].mask(df["missing_ageb"])
        df["grid_analysis"] = df["grid"].mask(df["missing_grid"])
        df["postal_code_analysis"] = df["postal_code"].where(df["postal_status"].eq("valid_plausible"))
        frames.append(df)

    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return CleanResult(asset.source_edition, CANONICAL_EDITION.get(asset.source_edition, asset.source_edition), frame)


def write_clean_partition(result: CleanResult, destination: Path) -> Path:
    folder = destination / f"edition={result.canonical_edition}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "part-000.parquet"
    result.frame.to_parquet(target, index=False)
    metadata = {
        "source_edition": result.edition,
        "canonical_edition": result.canonical_edition,
        "rows": int(len(result.frame)),
        "establishments": int(result.frame["establishments"].sum()) if not result.frame.empty else 0,
    }
    (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def weighted_share(frame: pd.DataFrame, mask: pd.Series) -> float:
    total = float(frame["establishments"].sum())
    return float(frame.loc[mask, "establishments"].sum() / total) if total > 0 else float("nan")


def concentration(frame: pd.DataFrame, key: str) -> dict[str, float]:
    counts = frame.groupby(key, dropna=False)["establishments"].sum().astype(float)
    total = counts.sum()
    if total <= 0:
        return {"hhi": np.nan, "shannon": np.nan, "effective_categories": np.nan}
    p = counts / total
    positive = p[p > 0]
    hhi = float(np.square(p).sum())
    shannon = float(-(positive * np.log(positive)).sum())
    return {"hhi": hhi, "shannon": shannon, "effective_categories": float(np.exp(shannon))}
