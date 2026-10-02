from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


def load_staged(staged_root: Path) -> pd.DataFrame:
    files = sorted(staged_root.glob("edition=*/part-*.parquet"))
    if not files:
        raise FileNotFoundError(f"no staged DENUE parquet partitions under {staged_root}")
    frames = [pd.read_parquet(path) for path in files]
    frame = pd.concat(frames, ignore_index=True)
    frame["edition_date"] = pd.to_datetime(frame["edition_date"])
    return frame


def _weighted_share(group: pd.DataFrame, mask: pd.Series) -> float:
    total = float(group["establishments"].sum())
    if total <= 0:
        return float("nan")
    return float(group.loc[mask, "establishments"].sum() / total)


def _diversity(group: pd.DataFrame, key: str) -> tuple[float, float, float]:
    counts = group.groupby(key, dropna=False)["establishments"].sum().astype(float)
    total = counts.sum()
    if total <= 0:
        return (float("nan"), float("nan"), float("nan"))
    p = counts / total
    positive = p[p > 0]
    hhi = float(np.square(p).sum())
    shannon = float(-(positive * np.log(positive)).sum())
    return hhi, shannon, float(np.exp(shannon))


def edition_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for keys, group in frame.groupby(["canonical_edition", "edition_date", "rebenchmark"], dropna=False):
        edition, date, rebenchmark = keys
        hhi, shannon, effective = _diversity(group, "sector")
        rows.append({
            "canonical_edition": edition,
            "edition_date": date,
            "rebenchmark": bool(rebenchmark),
            "establishments": int(group["establishments"].sum()),
            "municipalities": int(group["municipality_code"].nunique()),
            "active_agebs": int(group.loc[~group["missing_ageb"], ["municipality_code", "ageb_analysis"]].drop_duplicates().shape[0]),
            "active_grids": int(group.loc[~group["missing_grid"], ["municipality_code", "grid_analysis"]].drop_duplicates().shape[0]),
            "sector_hhi": hhi,
            "sector_shannon": shannon,
            "effective_sectors": effective,
            "phone_share": _weighted_share(group, group["has_phone"].fillna(False)),
            "email_share": _weighted_share(group, group["has_email"].fillna(False)),
            "web_share": _weighted_share(group, group["has_web"].fillna(False)),
            "missing_ageb_share": _weighted_share(group, group["missing_ageb"]),
            "missing_grid_share": _weighted_share(group, group["missing_grid"]),
            "postal_problem_share": _weighted_share(group, ~group["postal_status"].eq("valid_plausible")),
        })
    out = pd.DataFrame(rows).sort_values("edition_date").reset_index(drop=True)
    out["growth_pct"] = out["establishments"].pct_change() * 100
    out["log_growth"] = np.log(out["establishments"]).diff()
    out["growth_ex_rebenchmark"] = out["growth_pct"].where(~out["rebenchmark"])
    return out


def municipality_summary(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby(["canonical_edition", "edition_date", "rebenchmark", "municipality_code", "municipality_name"], dropna=False)["establishments"]
        .sum()
        .rename("establishments")
        .reset_index()
        .sort_values(["municipality_code", "edition_date"])
    )
    grouped["growth_pct"] = grouped.groupby("municipality_code")["establishments"].pct_change() * 100
    grouped["growth_ex_rebenchmark"] = grouped["growth_pct"].where(~grouped["rebenchmark"])
    state_totals = grouped.groupby("canonical_edition")["establishments"].transform("sum")
    grouped["state_share"] = grouped["establishments"] / state_totals
    grouped["rank_state"] = grouped.groupby("canonical_edition")["establishments"].rank(method="dense", ascending=False)
    return grouped


def sector_summary(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby(["canonical_edition", "edition_date", "municipality_code", "municipality_name", "sector"], dropna=False)["establishments"]
        .sum()
        .rename("establishments")
        .reset_index()
    )
    totals = grouped.groupby(["canonical_edition", "municipality_code"])["establishments"].transform("sum")
    grouped["local_share"] = grouped["establishments"] / totals
    state_sector = grouped.groupby(["canonical_edition", "sector"])["establishments"].transform("sum")
    state_total = grouped.groupby("canonical_edition")["establishments"].transform("sum")
    grouped["state_sector_share"] = state_sector / state_total
    grouped["location_quotient"] = grouped["local_share"] / grouped["state_sector_share"].replace(0, np.nan)
    return grouped


def size_summary(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby(["canonical_edition", "edition_date", "municipality_code", "municipality_name", "size_band"], dropna=False)["establishments"]
        .sum()
        .rename("establishments")
        .reset_index()
    )
    totals = grouped.groupby(["canonical_edition", "municipality_code"])["establishments"].transform("sum")
    grouped["share"] = grouped["establishments"] / totals
    return grouped


def detect_growth_outliers(series: pd.DataFrame, group_key: str | None = None) -> pd.DataFrame:
    out = series.copy()
    target = "growth_ex_rebenchmark"
    if group_key is None:
        med = out[target].median(skipna=True)
        mad = (out[target] - med).abs().median(skipna=True)
        out["robust_z_growth"] = 0.6745 * (out[target] - med) / mad if mad and np.isfinite(mad) else np.nan
    else:
        def _score(s: pd.Series) -> pd.Series:
            med = s.median(skipna=True)
            mad = (s - med).abs().median(skipna=True)
            return 0.6745 * (s - med) / mad if mad and np.isfinite(mad) else pd.Series(np.nan, index=s.index)
        out["robust_z_growth"] = out.groupby(group_key, group_keys=False)[target].apply(_score)
    out["growth_outlier"] = out["robust_z_growth"].abs() >= 3.5
    return out


@dataclass(frozen=True)
class EdaArtifacts:
    state: pd.DataFrame
    municipalities: pd.DataFrame
    sectors: pd.DataFrame
    sizes: pd.DataFrame


def build_eda(frame: pd.DataFrame) -> EdaArtifacts:
    state = detect_growth_outliers(edition_summary(frame))
    municipalities = detect_growth_outliers(municipality_summary(frame), "municipality_code")
    return EdaArtifacts(state=state, municipalities=municipalities, sectors=sector_summary(frame), sizes=size_summary(frame))


def write_eda(artifacts: EdaArtifacts, output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "state": output / "state_timeseries.parquet",
        "municipalities": output / "municipality_timeseries.parquet",
        "sectors": output / "municipality_sector.parquet",
        "sizes": output / "municipality_size.parquet",
    }
    artifacts.state.to_parquet(paths["state"], index=False)
    artifacts.municipalities.to_parquet(paths["municipalities"], index=False)
    artifacts.sectors.to_parquet(paths["sectors"], index=False)
    artifacts.sizes.to_parquet(paths["sizes"], index=False)
    return paths
