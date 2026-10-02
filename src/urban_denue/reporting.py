from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _fmt_pct(value: float) -> str:
    return "n.d." if pd.isna(value) else f"{value:.2f}%"


def municipality_report(processed_root: Path, reports_root: Path, municipality_code: str = "012") -> Path:
    core = processed_root / "eda_core"
    spatial = processed_root / "spatial_eda"
    municipalities = pd.read_parquet(core / "municipality_timeseries.parquet")
    sectors = pd.read_parquet(core / "municipality_sector.parquet")
    poly = pd.read_parquet(spatial / "polycentricity.parquet")

    series = municipalities.loc[municipalities["municipality_code"].eq(municipality_code)].sort_values("edition_date")
    if series.empty:
        raise KeyError(f"municipality code not found: {municipality_code}")
    name = str(series.iloc[-1]["municipality_name"])
    latest = series.iloc[-1]
    first = series.iloc[0]
    latest_edition = latest["canonical_edition"]

    sector_latest = sectors.loc[
        sectors["municipality_code"].eq(municipality_code) & sectors["canonical_edition"].eq(latest_edition)
    ].sort_values("establishments", ascending=False)
    poly_latest = poly.loc[
        poly["municipality_code"].eq(municipality_code) & poly["canonical_edition"].eq(latest_edition)
    ]

    destination = reports_root / f"municipality_{municipality_code}"
    destination.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(series["edition_date"], series["establishments"], marker="o")
    for _, row in series.loc[series["rebenchmark"]].iterrows():
        ax.axvline(row["edition_date"], linestyle="--", linewidth=1)
    ax.set_title(f"DENUE — {name}: establecimientos registrados")
    ax.set_xlabel("Edición")
    ax.set_ylabel("Establecimientos")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    trend_path = destination / "establishments_timeseries.png"
    fig.savefig(trend_path, dpi=150)
    plt.close(fig)

    top = sector_latest.head(10).sort_values("establishments")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top["sector"].astype(str), top["establishments"])
    ax.set_title(f"DENUE — {name}: principales sectores, {latest_edition}")
    ax.set_xlabel("Establecimientos")
    ax.set_ylabel("Sector SCIAN")
    fig.tight_layout()
    sector_chart = destination / "top_sectors.png"
    fig.savefig(sector_chart, dpi=150)
    plt.close(fig)

    total_change = (latest["establishments"] / first["establishments"] - 1) * 100 if first["establishments"] else float("nan")
    lines = [
        f"# DENUE — {name}",
        "",
        "## Resumen descriptivo",
        "",
        f"- Primera edición observada: **{first['canonical_edition']}** — {int(first['establishments']):,} establecimientos.",
        f"- Última edición observada: **{latest_edition}** — {int(latest['establishments']):,} establecimientos.",
        f"- Cambio acumulado del stock registrado entre ambas ediciones: **{_fmt_pct(total_change)}**.",
        f"- Participación en el total estatal en la última edición: **{latest['state_share'] * 100:.2f}%**.",
        "",
        "## Sectores con mayor stock en la última edición",
        "",
        "| SCIAN sector | Establecimientos | Participación local | LQ estatal |",
        "|---:|---:|---:|---:|",
    ]
    for _, row in sector_latest.head(10).iterrows():
        lines.append(
            f"| {row['sector']} | {int(row['establishments']):,} | {row['local_share'] * 100:.2f}% | {row['location_quotient']:.3f} |"
        )

    if not poly_latest.empty:
        row = poly_latest.iloc[0]
        lines.extend([
            "",
            "## Estructura territorial por cuadrícula",
            "",
            f"- Cuadrículas activas: **{int(row['active_grids'])}**.",
            f"- Participación de la cuadrícula principal: **{row['top1_share'] * 100:.2f}%**.",
            f"- Participación de las 10 cuadrículas principales: **{row['top10_share'] * 100:.2f}%**.",
            f"- Número efectivo de nodos por HHI: **{row['effective_hhi_grids']:.2f}**.",
            f"- Gini espacial del stock por cuadrícula: **{row['grid_gini']:.3f}**.",
        ])

    lines.extend([
        "",
        "## Lectura metodológica",
        "",
        "Los cambios entre ediciones describen variaciones del **stock registrado por DENUE**. No deben interpretarse automáticamente como aperturas, cierres o crecimiento causal. Las ediciones 2015-01, 2019-11 y 2024-11 están marcadas como rebenchmarks de cobertura y deben tratarse por separado en análisis longitudinal.",
        "",
        "Las apariciones/desapariciones territoriales son proxies agregados por AGEB/cuadrícula porque este paquete compacto no conserva identificadores individuales de establecimientos.",
        "",
        f"![Serie histórica]({trend_path.name})",
        "",
        f"![Sectores]({sector_chart.name})",
    ])
    report_path = destination / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def state_report(processed_root: Path, reports_root: Path) -> Path:
    state = pd.read_parquet(processed_root / "eda_core" / "state_timeseries.parquet").sort_values("edition_date")
    destination = reports_root / "state"
    destination.mkdir(parents=True, exist_ok=True)
    latest = state.iloc[-1]
    first = state.iloc[0]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(state["edition_date"], state["establishments"], marker="o")
    for _, row in state.loc[state["rebenchmark"]].iterrows():
        ax.axvline(row["edition_date"], linestyle="--", linewidth=1)
    ax.set_title("DENUE Sinaloa — stock registrado")
    ax.set_xlabel("Edición")
    ax.set_ylabel("Establecimientos")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    chart = destination / "state_timeseries.png"
    fig.savefig(chart, dpi=150)
    plt.close(fig)
    change = (latest["establishments"] / first["establishments"] - 1) * 100
    text = f"""# DENUE — Sinaloa\n\n- Primera edición: **{first['canonical_edition']}**, {int(first['establishments']):,} establecimientos.\n- Última edición: **{latest['canonical_edition']}**, {int(latest['establishments']):,} establecimientos.\n- Cambio acumulado del stock registrado: **{change:.2f}%**.\n- Sectores efectivos (Shannon) en la última edición: **{latest['effective_sectors']:.2f}**.\n\nLos saltos asociados con rebenchmarks se conservan pero no se interpretan como crecimiento económico puro.\n\n![Serie histórica]({chart.name})\n"""
    report = destination / "report.md"
    report.write_text(text, encoding="utf-8")
    return report
