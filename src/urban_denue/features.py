from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


def add_temporal_features(panel: pd.DataFrame, geography: str) -> pd.DataFrame:
    out = panel.copy().sort_values(["municipality_key", geography, "edition_date"])
    group = out.groupby(["municipality_key", geography], group_keys=False)
    out["lag_stock_1"] = group["establishments"].shift(1)
    out["lag_stock_2"] = group["establishments"].shift(2)
    out["lead_stock_1"] = group["establishments"].shift(-1)
    out["log_stock"] = np.log1p(out["establishments"])
    out["lag_log_stock_1"] = group["log_stock"].shift(1)
    out["dlog_stock"] = out["log_stock"] - out["lag_log_stock_1"]
    out["growth_pct_clean"] = out["pct_change"].where(~out["transition_rebenchmark"])
    out["years_since_first_active"] = (
        (out["edition_date"] - out["first_active_date"]).dt.days / 365.25
    ).clip(lower=0)
    out["post_2015_rebenchmark"] = out["edition_date"] >= pd.Timestamp("2015-01-01")
    out["post_2019_rebenchmark"] = out["edition_date"] >= pd.Timestamp("2019-11-01")
    out["post_2024_rebenchmark"] = out["edition_date"] >= pd.Timestamp("2024-11-01")
    first_date = out["edition_date"].min()
    out["months_from_start"] = ((out["edition_date"].dt.year - first_date.year) * 12 + (out["edition_date"].dt.month - first_date.month)).astype("int16")
    active_counts = group["active"].transform("sum")
    periods = group["active"].transform("size")
    out["active_share_history"] = active_counts / periods
    out["balanced_active_panel"] = active_counts.eq(periods)
    out["model_transition_ok"] = (~out["transition_rebenchmark"]) & out["lag_stock_1"].notna()
    return out


def geography_composition(frame: pd.DataFrame, geography: str) -> pd.DataFrame:
    source = frame.loc[frame[geography].notna()].copy()
    keys = ["canonical_edition", "edition_date", "municipality_key", "municipality_code", "municipality_name", geography]
    rows: list[dict] = []
    for values, group in source.groupby(keys, dropna=False):
        total = float(group["establishments"].sum())
        row = dict(zip(keys, values))
        if total <= 0:
            row.update({"phone_share":np.nan,"email_share":np.nan,"web_share":np.nan,"size_band_1_share":np.nan,"size_band_1_2_share":np.nan})
        else:
            weight = group["establishments"].astype(float)
            row.update({
                "phone_share": float(weight[group["has_phone"].fillna(False)].sum() / total),
                "email_share": float(weight[group["has_email"].fillna(False)].sum() / total),
                "web_share": float(weight[group["has_web"].fillna(False)].sum() / total),
                "size_band_1_share": float(weight[group["size_band"].eq(1)].sum() / total),
                "size_band_1_2_share": float(weight[group["size_band"].isin([1,2])].sum() / total),
            })
        rows.append(row)
    return pd.DataFrame(rows)


def geography_sector_lq(frame: pd.DataFrame, geography: str) -> pd.DataFrame:
    source = frame.loc[frame[geography].notna()].copy()
    local = (
        source.groupby(["canonical_edition", "edition_date", "municipality_key", "municipality_code", "municipality_name", geography, "sector"], dropna=False)["establishments"]
        .sum().rename("establishments").reset_index()
    )
    local_total = local.groupby(["canonical_edition", "municipality_key", geography])["establishments"].transform("sum")
    muni_sector = local.groupby(["canonical_edition", "municipality_key", "sector"])["establishments"].transform("sum")
    muni_total = local.groupby(["canonical_edition", "municipality_key"])["establishments"].transform("sum")
    local["local_share"] = local["establishments"] / local_total.replace(0, np.nan)
    local["municipality_sector_share"] = muni_sector / muni_total.replace(0, np.nan)
    local["location_quotient"] = local["local_share"] / local["municipality_sector_share"].replace(0, np.nan)
    local["specialized_lq_gt_1"] = local["location_quotient"] > 1
    local["strong_specialization_lq_gt_1_5"] = local["location_quotient"] > 1.5
    return local


def queen_neighbor_features(grid_features: pd.DataFrame, geometry: gpd.GeoDataFrame) -> pd.DataFrame:
    from libpysal.weights import Queen

    out_parts: list[pd.DataFrame] = []
    keys = ["canonical_edition", "edition_date", "municipality_key"]
    for values, group in grid_features.groupby(keys, dropna=False):
        muni = values[2]
        geo = geometry.loc[geometry["municipality_key"].eq(muni), ["grid_analysis", "geometry"]].merge(group, on="grid_analysis", how="inner")
        if geo.empty:
            out_parts.append(group)
            continue
        geo = gpd.GeoDataFrame(geo, geometry="geometry", crs=geometry.crs).reset_index(drop=True)
        try:
            w = Queen.from_dataframe(geo, use_index=False, silence_warnings=True)
        except Exception:
            out_parts.append(group)
            continue
        stock = geo["establishments"].to_numpy(dtype=float)
        neighbor_sum = np.zeros(len(geo), dtype=float)
        neighbor_mean = np.full(len(geo), np.nan, dtype=float)
        neighbor_degree = np.zeros(len(geo), dtype=int)
        for idx, neighbors in w.neighbors.items():
            neighbor_degree[idx] = len(neighbors)
            if neighbors:
                vals = stock[np.asarray(neighbors, dtype=int)]
                neighbor_sum[idx] = vals.sum()
                neighbor_mean[idx] = vals.mean()
        geo["queen_neighbors"] = neighbor_degree
        geo["neighbor_stock_sum"] = neighbor_sum
        geo["neighbor_stock_mean"] = neighbor_mean
        geo["relative_to_neighbor_mean"] = geo["establishments"] / pd.Series(neighbor_mean).replace(0, np.nan)
        out_parts.append(pd.DataFrame(geo.drop(columns="geometry")))
    return pd.concat(out_parts, ignore_index=True) if out_parts else grid_features.copy()


def build_model_features(
    frame: pd.DataFrame,
    panel: pd.DataFrame,
    diversity: pd.DataFrame,
    geography: str,
) -> pd.DataFrame:
    temporal = add_temporal_features(panel, geography)
    composition = geography_composition(frame, geography)
    join_keys = ["canonical_edition", "edition_date", "municipality_key", "municipality_code", "municipality_name", geography]
    out = temporal.merge(composition, on=join_keys, how="left")
    diversity_cols = join_keys + ["sectors", "scian6_classes", "sector_hhi", "sector_shannon", "effective_sectors"]
    out = out.merge(diversity[diversity_cols], on=join_keys, how="left")
    out["log_effective_sectors"] = np.log1p(out["effective_sectors"])
    out["high_concentration_hhi"] = out["sector_hhi"] >= 0.25
    return out


def write_feature_store(features: dict[str, pd.DataFrame], output: Path) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for name, frame in features.items():
        path = output / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        paths[name] = str(path)
    return paths
