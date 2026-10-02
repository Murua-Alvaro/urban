from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from panel import REBENCHMARK_EDITIONS, concentration_metrics


def _weighted_share(frame: pd.DataFrame, mask: pd.Series) -> float:
    total = float(frame["establishments"].sum())
    if total <= 0:
        return float("nan")
    return float(frame.loc[mask, "establishments"].sum() / total)


def _growth_columns(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    frame = frame.sort_values(group_cols + ["edition_date"]).copy()
    grouped = frame.groupby(group_cols, dropna=False) if group_cols else None
    if grouped is None:
        frame["previous_establishments"] = frame["establishments"].shift(1)
        frame["previous_date"] = frame["edition_date"].shift(1)
    else:
        frame["previous_establishments"] = grouped["establishments"].shift(1)
        frame["previous_date"] = grouped["edition_date"].shift(1)
    frame["growth_pct"] = (frame["establishments"] / frame["previous_establishments"] - 1.0) * 100.0
    days = (frame["edition_date"] - frame["previous_date"]).dt.days
    ratio = frame["establishments"] / frame["previous_establishments"]
    frame["annualized_growth_pct"] = np.where(
        (days > 0) & (ratio > 0),
        (np.power(ratio, 365.25 / days) - 1.0) * 100.0,
        np.nan,
    )
    frame["large_jump"] = frame["growth_pct"].abs().ge(5.0)
    return frame


def summarize_state(df: pd.DataFrame) -> dict:
    total = int(df["establishments"].sum())
    diversity = concentration_metrics(df, "sector")
    valid_ageb = df.loc[~df["missing_ageb"], ["municipality_code", "ageb"]].drop_duplicates()
    valid_grid = df.loc[~df["missing_grid"], "grid"].drop_duplicates()
    return {
        "source_edition": df["source_edition"].iat[0],
        "edition_date": df["edition_date"].iat[0],
        "rebenchmark": bool(df["rebenchmark"].iat[0]),
        "establishments": total,
        "active_municipalities": int(df["municipality_code"].nunique()),
        "active_ageb_assignments": int(len(valid_ageb)),
        "active_grid_cells": int(len(valid_grid)),
        "missing_ageb_share": _weighted_share(df, df["missing_ageb"]),
        "missing_grid_share": _weighted_share(df, df["missing_grid"]),
        "missing_postal_share": _weighted_share(df, df["missing_postal_code"]),
        "postal_prefix_outlier_share": _weighted_share(
            df, (~df["missing_postal_code"]) & (~df["postal_prefix_plausible_sinaloa"])
        ),
        "phone_share": _weighted_share(df, df["has_phone"]),
        "email_share": _weighted_share(df, df["has_email"]),
        "web_share": _weighted_share(df, df["has_web"]),
        "sector_hhi": diversity["hhi"],
        "sector_shannon": diversity["shannon"],
        "effective_sectors": diversity["effective_categories"],
    }


def summarize_municipalities(df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for (code, name), g in df.groupby(["municipality_code", "municipality_name"], dropna=False, observed=True):
        diversity = concentration_metrics(g, "sector")
        rows.append(
            {
                "source_edition": g["source_edition"].iat[0],
                "edition_date": g["edition_date"].iat[0],
                "rebenchmark": bool(g["rebenchmark"].iat[0]),
                "municipality_code": code,
                "municipality_name": name,
                "establishments": int(g["establishments"].sum()),
                "active_agebs": int(g.loc[~g["missing_ageb"], "ageb"].nunique()),
                "active_grids": int(g.loc[~g["missing_grid"], "grid"].nunique()),
                "missing_ageb_share": _weighted_share(g, g["missing_ageb"]),
                "missing_grid_share": _weighted_share(g, g["missing_grid"]),
                "missing_postal_share": _weighted_share(g, g["missing_postal_code"]),
                "postal_prefix_outlier_share": _weighted_share(
                    g, (~g["missing_postal_code"]) & (~g["postal_prefix_plausible_sinaloa"])
                ),
                "phone_share": _weighted_share(g, g["has_phone"]),
                "email_share": _weighted_share(g, g["has_email"]),
                "web_share": _weighted_share(g, g["has_web"]),
                "sector_hhi": diversity["hhi"],
                "sector_shannon": diversity["shannon"],
                "effective_sectors": diversity["effective_categories"],
            }
        )
    return rows


def _plot_series(df: pd.DataFrame, value: str, title: str, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["edition_date"], df[value], marker="o", linewidth=1.5)
    for _, row in df.loc[df["rebenchmark"]].iterrows():
        ax.axvline(row["edition_date"], linestyle="--", alpha=0.45)
    ax.set_title(title)
    ax.set_xlabel("Edición DENUE")
    ax.set_ylabel(value.replace("_", " ").title())
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible EDA on canonical DENUE Parquet partitions.")
    parser.add_argument("--processed", type=Path, default=Path("var/denue/processed"))
    parser.add_argument("--output", type=Path, default=Path("var/denue/eda"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted((args.processed / "editions").glob("denue_*.parquet"))
    if not parquet_files:
        raise FileNotFoundError("No DENUE Parquet partitions found. Run build_panel.py first.")

    state_rows: list[dict] = []
    municipality_rows: list[dict] = []
    sector_frames: list[pd.DataFrame] = []
    scian6_frames: list[pd.DataFrame] = []
    size_frames: list[pd.DataFrame] = []

    for path in parquet_files:
        df = pd.read_parquet(path)
        df["edition_date"] = pd.to_datetime(df["edition_date"])
        state_rows.append(summarize_state(df))
        municipality_rows.extend(summarize_municipalities(df))

        dimensions = [
            ("sector", sector_frames),
            ("scian6", scian6_frames),
            ("size_band", size_frames),
        ]
        for dimension, bucket in dimensions:
            agg = (
                df.groupby(["source_edition", "edition_date", "municipality_code", "municipality_name", dimension],
                           dropna=False, observed=True)["establishments"]
                .sum()
                .reset_index()
            )
            totals = agg.groupby(["source_edition", "municipality_code"], observed=True)["establishments"].transform("sum")
            agg["share"] = agg["establishments"] / totals
            bucket.append(agg)

    state = _growth_columns(pd.DataFrame(state_rows), [])
    municipalities = _growth_columns(pd.DataFrame(municipality_rows), ["municipality_code"])
    sectors = pd.concat(sector_frames, ignore_index=True)
    scian6 = pd.concat(scian6_frames, ignore_index=True)
    sizes = pd.concat(size_frames, ignore_index=True)

    state.to_csv(args.output / "state_timeseries.csv", index=False)
    municipalities.to_csv(args.output / "municipality_timeseries.csv", index=False)
    sectors.to_parquet(args.output / "sector_timeseries.parquet", index=False, compression="zstd")
    scian6.to_parquet(args.output / "scian6_timeseries.parquet", index=False, compression="zstd")
    sizes.to_csv(args.output / "size_timeseries.csv", index=False)

    quality_cols = [
        "source_edition", "edition_date", "missing_ageb_share", "missing_grid_share",
        "missing_postal_share", "postal_prefix_outlier_share", "phone_share", "email_share", "web_share"
    ]
    state[quality_cols].to_csv(args.output / "quality_by_edition.csv", index=False)

    jump_cols = ["source_edition", "edition_date", "establishments", "growth_pct", "annualized_growth_pct", "rebenchmark", "large_jump"]
    state[jump_cols].to_csv(args.output / "state_growth_breaks.csv", index=False)

    _plot_series(state, "establishments", "Sinaloa · establecimientos registrados en DENUE", args.output / "state_establishments.png")
    mazatlan = municipalities.loc[municipalities["municipality_code"].eq("25_012")].copy()
    if not mazatlan.empty:
        _plot_series(mazatlan, "establishments", "Mazatlán · establecimientos registrados en DENUE", args.output / "mazatlan_establishments.png")
        _plot_series(mazatlan, "effective_sectors", "Mazatlán · diversidad sectorial efectiva", args.output / "mazatlan_diversity.png")

    print(f"EDA complete: {args.output}")
    print(f"State editions: {len(state)} | municipality-editions: {len(municipalities)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
