from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _entropy(parts: pd.Series) -> float:
    values = parts[parts > 0].to_numpy(dtype=float)
    if not len(values):
        return float("nan")
    return float(-(values * np.log(values)).sum())


def build_features(df: pd.DataFrame, level: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    geography_col = level
    missing_col = f"missing_{level}"
    if geography_col not in df.columns or missing_col not in df.columns:
        raise KeyError(f"Missing required columns for level={level}")

    work = df.loc[~df[missing_col]].copy()
    keys = ["source_edition", "edition_date", "municipality_code", "municipality_name", geography_col]

    totals = (
        work.groupby(keys, observed=True, dropna=False)["establishments"]
        .sum()
        .rename("establishments")
        .reset_index()
    )

    contacts = work.copy()
    for col in ["has_phone", "has_email", "has_web"]:
        contacts[f"{col}_weighted"] = contacts[col].astype(int) * contacts["establishments"]
    contacts = (
        contacts.groupby(keys, observed=True, dropna=False)
        .agg(
            phone_weighted=("has_phone_weighted", "sum"),
            email_weighted=("has_email_weighted", "sum"),
            web_weighted=("has_web_weighted", "sum"),
            scian6_count=("scian6", "nunique"),
        )
        .reset_index()
    )

    sector = (
        work.groupby(keys + ["sector"], observed=True, dropna=False)["establishments"]
        .sum()
        .rename("sector_establishments")
        .reset_index()
    )
    sector = sector.merge(totals, on=keys, how="left", validate="many_to_one")
    sector["sector_share"] = sector["sector_establishments"] / sector["establishments"]

    diversity = (
        sector.groupby(keys, observed=True, dropna=False)
        .agg(
            sector_count=("sector", "nunique"),
            sector_hhi=("sector_share", lambda s: float(np.square(s).sum())),
            sector_shannon=("sector_share", _entropy),
        )
        .reset_index()
    )
    diversity["effective_sectors"] = np.exp(diversity["sector_shannon"])

    features = totals.merge(contacts, on=keys, how="left", validate="one_to_one")
    features = features.merge(diversity, on=keys, how="left", validate="one_to_one")
    denom = features["establishments"].replace(0, np.nan)
    features["phone_share"] = features["phone_weighted"] / denom
    features["email_share"] = features["email_weighted"] / denom
    features["web_share"] = features["web_weighted"] / denom
    features = features.drop(columns=["phone_weighted", "email_weighted", "web_weighted"])

    municipality_sector = (
        work.groupby(["source_edition", "municipality_code", "sector"], observed=True)["establishments"]
        .sum()
        .rename("municipality_sector_establishments")
        .reset_index()
    )
    municipality_total = (
        work.groupby(["source_edition", "municipality_code"], observed=True)["establishments"]
        .sum()
        .rename("municipality_establishments")
        .reset_index()
    )
    municipality_sector = municipality_sector.merge(
        municipality_total,
        on=["source_edition", "municipality_code"],
        how="left",
        validate="many_to_one",
    )
    municipality_sector["municipality_sector_share"] = (
        municipality_sector["municipality_sector_establishments"]
        / municipality_sector["municipality_establishments"]
    )

    state_sector = (
        work.groupby(["source_edition", "sector"], observed=True)["establishments"]
        .sum()
        .rename("state_sector_establishments")
        .reset_index()
    )
    state_total = (
        work.groupby(["source_edition"], observed=True)["establishments"]
        .sum()
        .rename("state_establishments")
        .reset_index()
    )
    state_sector = state_sector.merge(state_total, on="source_edition", how="left", validate="many_to_one")
    state_sector["state_sector_share"] = state_sector["state_sector_establishments"] / state_sector["state_establishments"]

    lq = sector.merge(
        municipality_sector,
        on=["source_edition", "municipality_code", "sector"],
        how="left",
        validate="many_to_one",
    ).merge(
        state_sector,
        on=["source_edition", "sector"],
        how="left",
        validate="many_to_one",
    )
    lq["lq_municipality"] = lq["sector_share"] / lq["municipality_sector_share"]
    lq["lq_state"] = lq["sector_share"] / lq["state_sector_share"]
    lq["specialized_municipality"] = lq["lq_municipality"].ge(1.25)
    lq["specialized_state"] = lq["lq_state"].ge(1.25)

    keep_lq = keys + [
        "sector", "sector_establishments", "sector_share",
        "municipality_sector_share", "state_sector_share",
        "lq_municipality", "lq_state", "specialized_municipality", "specialized_state",
    ]
    return features, lq[keep_lq]


def add_grid_dynamics(features: pd.DataFrame) -> pd.DataFrame:
    keys = ["municipality_code", "grid"]
    editions = (
        features[["source_edition", "edition_date"]]
        .drop_duplicates()
        .sort_values("edition_date")
    )
    geos = features[keys + ["municipality_name"]].drop_duplicates()
    balanced = geos.assign(_key=1).merge(editions.assign(_key=1), on="_key").drop(columns="_key")
    balanced = balanced.merge(
        features,
        on=["source_edition", "edition_date", "municipality_code", "municipality_name", "grid"],
        how="left",
        validate="one_to_one",
    )
    numeric_zero = ["establishments", "sector_count", "scian6_count"]
    for col in numeric_zero:
        balanced[col] = balanced[col].fillna(0)

    balanced = balanced.sort_values(keys + ["edition_date"]).reset_index(drop=True)
    grouped = balanced.groupby(keys, observed=True, dropna=False)
    balanced["previous_establishments"] = grouped["establishments"].shift(1)
    balanced["previous_date"] = grouped["edition_date"].shift(1)
    balanced["next_establishments"] = grouped["establishments"].shift(-1)
    balanced["next_date"] = grouped["edition_date"].shift(-1)
    balanced["stock_change"] = balanced["establishments"] - balanced["previous_establishments"]
    balanced["growth_pct"] = np.where(
        balanced["previous_establishments"] > 0,
        (balanced["establishments"] / balanced["previous_establishments"] - 1.0) * 100.0,
        np.nan,
    )

    prev = balanced["previous_establishments"]
    cur = balanced["establishments"]
    conditions = [
        prev.isna(),
        prev.eq(0) & cur.gt(0),
        prev.gt(0) & cur.eq(0),
        prev.gt(0) & cur.gt(0) & balanced["growth_pct"].gt(10),
        prev.gt(0) & cur.gt(0) & balanced["growth_pct"].lt(-10),
    ]
    choices = ["first_observation", "activation", "deactivation", "expanding", "contracting"]
    balanced["transition"] = np.select(conditions, choices, default="stable")
    balanced["geo_id"] = balanced["municipality_code"].astype(str) + "|" + balanced["grid"].astype(str)
    balanced["log1p_establishments"] = np.log1p(balanced["establishments"])
    balanced["next_log1p_establishments"] = np.log1p(balanced["next_establishments"])
    return balanced


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DENUE territorial feature store and LQ tables.")
    parser.add_argument("--processed", type=Path, default=Path("var/denue/processed"))
    parser.add_argument("--output", type=Path, default=Path("var/denue/analysis"))
    parser.add_argument("--level", choices=["grid", "ageb"], default="grid")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    feature_parts: list[pd.DataFrame] = []
    lq_parts: list[pd.DataFrame] = []
    for path in sorted((args.processed / "editions").glob("denue_*.parquet")):
        df = pd.read_parquet(path)
        df["edition_date"] = pd.to_datetime(df["edition_date"])
        features, lq = build_features(df, args.level)
        feature_parts.append(features)
        lq_parts.append(lq)
        print(f"{path.name}: {len(features):,} {args.level}s / {len(lq):,} LQ rows")

    features = pd.concat(feature_parts, ignore_index=True)
    lq = pd.concat(lq_parts, ignore_index=True)

    if args.level == "grid":
        features = add_grid_dynamics(features)
        feature_name = "grid_features.parquet"
        lq_name = "grid_sector_lq.parquet"
        transition = (
            features.groupby(["source_edition", "edition_date", "municipality_code", "municipality_name", "transition"], observed=True)
            .size()
            .rename("grid_count")
            .reset_index()
        )
        transition.to_csv(args.output / "grid_transitions.csv", index=False)
    else:
        feature_name = "ageb_features.parquet"
        lq_name = "ageb_sector_lq.parquet"

    features.to_parquet(args.output / feature_name, index=False, compression="zstd")
    lq.to_parquet(args.output / lq_name, index=False, compression="zstd")
    print(f"Saved: {args.output / feature_name}")
    print(f"Saved: {args.output / lq_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
