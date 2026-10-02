from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from .catalog import data_root


def load_grid_geometry(extracted_root: Path) -> gpd.GeoDataFrame:
    path = data_root(extracted_root) / "cuadriculas.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    frames: list[gpd.GeoDataFrame] = []
    for municipality_key, feature_collection in payload.items():
        features = feature_collection.get("features", [])
        if not features:
            continue
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        gdf = gdf.rename(columns={"id": "grid_analysis"})
        gdf["municipality_key"] = municipality_key
        gdf["grid_key"] = gdf["municipality_key"].astype(str) + ":" + gdf["grid_analysis"].astype(str)
        frames.append(gdf[["municipality_key", "grid_analysis", "grid_key", "geometry"]])
    if not frames:
        return gpd.GeoDataFrame(columns=["municipality_key", "grid_analysis", "grid_key", "geometry"], geometry="geometry", crs="EPSG:4326")
    out = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs="EPSG:4326")


def add_grid_area(geometry: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    parts: list[gpd.GeoDataFrame] = []
    for _, group in geometry.groupby("municipality_key"):
        group = group.copy()
        utm = group.estimate_utm_crs()
        group["area_km2"] = np.nan if utm is None else group.to_crs(utm).geometry.area / 1_000_000
        parts.append(group)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs="EPSG:4326")


def _complete_panel(frame: pd.DataFrame, geography: str) -> pd.DataFrame:
    source = frame.loc[frame[geography].notna()].copy()
    totals = (
        source.groupby([
            "canonical_edition", "edition_date", "rebenchmark", "municipality_key",
            "municipality_code", "municipality_name", geography,
        ], dropna=False)["establishments"]
        .sum().rename("establishments").reset_index()
    )
    outputs: list[pd.DataFrame] = []
    for muni_key, group in totals.groupby("municipality_key"):
        meta = group[["municipality_key", "municipality_code", "municipality_name"]].drop_duplicates().iloc[0]
        municipality_editions = (
            frame.loc[frame["municipality_key"].eq(muni_key), ["canonical_edition", "edition_date", "rebenchmark"]]
            .drop_duplicates()
            .sort_values("edition_date")
        )
        geos = pd.DataFrame({geography: sorted(group[geography].dropna().astype(str).unique())})
        cross = municipality_editions.assign(_k=1).merge(geos.assign(_k=1), on="_k").drop(columns="_k")
        cross["municipality_key"] = muni_key
        cross["municipality_code"] = meta["municipality_code"]
        cross["municipality_name"] = meta["municipality_name"]
        merged = cross.merge(
            group,
            on=["canonical_edition", "edition_date", "rebenchmark", "municipality_key", "municipality_code", "municipality_name", geography],
            how="left",
        )
        merged["establishments"] = merged["establishments"].fillna(0).astype("int32")
        outputs.append(merged)
    if not outputs:
        return pd.DataFrame()
    out = pd.concat(outputs, ignore_index=True).sort_values(["municipality_key", geography, "edition_date"])
    out["lag_establishments"] = out.groupby(["municipality_key", geography])["establishments"].shift(1)
    out["net_change"] = out["establishments"] - out["lag_establishments"]
    out["pct_change"] = out["net_change"] / out["lag_establishments"].replace(0, np.nan) * 100
    out["active"] = out["establishments"] > 0
    out["appearance_proxy"] = (out["establishments"] > 0) & (out["lag_establishments"].fillna(0) == 0)
    out["disappearance_proxy"] = (out["establishments"] == 0) & (out["lag_establishments"].fillna(0) > 0)
    out["transition_rebenchmark"] = out["rebenchmark"].astype(bool)
    first = out.loc[out["active"]].groupby(["municipality_key", geography])["edition_date"].min().rename("first_active_date")
    last = out.loc[out["active"]].groupby(["municipality_key", geography])["edition_date"].max().rename("last_active_date")
    return out.merge(first, on=["municipality_key", geography], how="left").merge(last, on=["municipality_key", geography], how="left")


def grid_panel(frame: pd.DataFrame) -> pd.DataFrame:
    return _complete_panel(frame, "grid_analysis")


def ageb_panel(frame: pd.DataFrame) -> pd.DataFrame:
    return _complete_panel(frame, "ageb_analysis")


def geography_diversity(frame: pd.DataFrame, geography: str) -> pd.DataFrame:
    source = frame.loc[frame[geography].notna()].copy()
    keys = ["canonical_edition", "edition_date", "municipality_key", "municipality_code", "municipality_name", geography]
    rows: list[dict] = []
    for values, group in source.groupby(keys, dropna=False):
        counts = group.groupby("sector")["establishments"].sum().astype(float)
        total = counts.sum()
        p = counts / total if total > 0 else counts
        positive = p[p > 0]
        hhi = float(np.square(p).sum()) if total > 0 else np.nan
        shannon = float(-(positive * np.log(positive)).sum()) if total > 0 else np.nan
        row = dict(zip(keys, values))
        row.update({"establishments": int(total), "sectors": int((counts > 0).sum()), "scian6_classes": int(group.loc[group["establishments"] > 0, "scian6"].nunique()), "sector_hhi": hhi, "sector_shannon": shannon, "effective_sectors": float(np.exp(shannon)) if np.isfinite(shannon) else np.nan})
        rows.append(row)
    return pd.DataFrame(rows)


def _gini(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x) & (x >= 0)]
    if len(x) == 0 or x.sum() == 0:
        return float("nan")
    x = np.sort(x)
    n = len(x)
    return float((2 * np.sum(np.arange(1, n + 1) * x) / (n * x.sum())) - (n + 1) / n)


def polycentricity_summary(grid: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    keys = ["canonical_edition", "edition_date", "municipality_key", "municipality_code", "municipality_name"]
    for values, group in grid.groupby(keys, dropna=False):
        active = group.loc[group["establishments"] > 0, "establishments"].astype(float).sort_values(ascending=False)
        total = active.sum()
        row = dict(zip(keys, values))
        if total <= 0:
            row.update({"active_grids": 0, "grid_hhi": np.nan, "effective_hhi_grids": np.nan, "effective_entropy_grids": np.nan, "top1_share": np.nan, "top5_share": np.nan, "top10_share": np.nan, "grid_gini": np.nan, "rank_size_slope": np.nan})
        else:
            p = active / total
            hhi = float(np.square(p).sum())
            entropy = float(-(p * np.log(p)).sum())
            slope = float(np.polyfit(np.log(np.arange(1, len(active) + 1, dtype=float)), np.log(active.to_numpy()), 1)[0]) if len(active) >= 3 else np.nan
            row.update({"active_grids": int(len(active)), "grid_hhi": hhi, "effective_hhi_grids": float(1 / hhi) if hhi > 0 else np.nan, "effective_entropy_grids": float(np.exp(entropy)), "top1_share": float(active.head(1).sum() / total), "top5_share": float(active.head(5).sum() / total), "top10_share": float(active.head(10).sum() / total), "grid_gini": _gini(active.to_numpy()), "rank_size_slope": slope})
        rows.append(row)
    return pd.DataFrame(rows)


def global_moran_by_municipality(grid: pd.DataFrame, geometry: gpd.GeoDataFrame, permutations: int = 499, seed: int = 20261002) -> pd.DataFrame:
    from esda.moran import Moran
    from libpysal.weights import Queen
    rows: list[dict] = []
    np.random.seed(seed)
    keys = ["canonical_edition", "edition_date", "municipality_key", "municipality_code", "municipality_name"]
    for values, group in grid.groupby(keys, dropna=False):
        active = group.loc[group["establishments"] > 0, ["grid_analysis", "establishments"]]
        geo = geometry.loc[geometry["municipality_key"].eq(values[2])].merge(active, on="grid_analysis", how="inner")
        if len(geo) < 3:
            continue
        try:
            weights = Queen.from_dataframe(geo, use_index=False, silence_warnings=True)
            weights.transform = "r"
            if not any(weights.neighbors.values()):
                continue
            moran = Moran(geo["establishments"].to_numpy(dtype=float), weights, permutations=permutations)
        except Exception:
            continue
        row = dict(zip(keys, values))
        row.update({"n_grids": int(len(geo)), "moran_i": float(moran.I), "expected_i": float(moran.EI), "p_sim": float(moran.p_sim), "z_sim": float(moran.z_sim)})
        rows.append(row)
    return pd.DataFrame(rows)
