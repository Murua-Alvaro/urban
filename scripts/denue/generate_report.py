from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def pct_change(first: float, last: float) -> float:
    return (last / first - 1.0) * 100.0 if first else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a compact Markdown report from DENUE pipeline outputs.")
    parser.add_argument("--eda", type=Path, default=Path("var/denue/eda"))
    parser.add_argument("--analysis", type=Path, default=Path("var/denue/analysis"))
    parser.add_argument("--models", type=Path, default=Path("var/denue/models/grid_dynamics"))
    parser.add_argument("--output", type=Path, default=Path("var/denue/report.md"))
    args = parser.parse_args()

    state = pd.read_csv(args.eda / "state_timeseries.csv", parse_dates=["edition_date"])
    municipalities = pd.read_csv(args.eda / "municipality_timeseries.csv", parse_dates=["edition_date"])
    sectors = pd.read_parquet(args.eda / "sector_timeseries.parquet")

    state = state.sort_values("edition_date")
    first_state, last_state = state.iloc[0], state.iloc[-1]
    maz = municipalities.loc[municipalities["municipality_code"].eq("25_012")].sort_values("edition_date")
    first_maz, last_maz = maz.iloc[0], maz.iloc[-1]

    latest_edition = str(last_maz["source_edition"])
    latest_sectors = (
        sectors.loc[
            sectors["municipality_code"].eq("25_012")
            & sectors["source_edition"].eq(latest_edition)
        ]
        .sort_values("establishments", ascending=False)
        .head(10)
    )

    jumps = state.loc[state["large_jump"].fillna(False)].copy()
    quality = state.iloc[-1]

    lines = [
        "# DENUE histórico · reporte automático",
        "",
        "> Panel territorial derivado/agregado. Los cambios entre ediciones describen stock registrado y pueden incluir cambios de cobertura; no equivalen automáticamente a aperturas/cierres netos.",
        "",
        "## Sinaloa",
        "",
        f"- Primera edición: **{first_state['source_edition']}**, {int(first_state['establishments']):,} establecimientos.",
        f"- Última edición: **{last_state['source_edition']}**, {int(last_state['establishments']):,} establecimientos.",
        f"- Cambio acumulado entre ambos cortes: **{pct_change(first_state['establishments'], last_state['establishments']):.2f}%**.",
        f"- AGEB con actividad en el último corte: **{int(last_state['active_ageb_assignments']):,}** asignaciones municipio-AGEB.",
        f"- Cuadrículas activas en el último corte: **{int(last_state['active_grid_cells']):,}**.",
        "",
        "## Mazatlán",
        "",
        f"- {first_maz['source_edition']}: **{int(first_maz['establishments']):,}** establecimientos.",
        f"- {last_maz['source_edition']}: **{int(last_maz['establishments']):,}** establecimientos.",
        f"- Cambio acumulado: **{pct_change(first_maz['establishments'], last_maz['establishments']):.2f}%**.",
        f"- AGEB activas: **{int(first_maz['active_agebs'])} → {int(last_maz['active_agebs'])}**.",
        f"- Cuadrículas activas: **{int(first_maz['active_grids'])} → {int(last_maz['active_grids'])}**.",
        f"- Sectores efectivos (exp(entropía)): **{first_maz['effective_sectors']:.2f} → {last_maz['effective_sectors']:.2f}**.",
        f"- Presencia web ponderada en último corte: **{last_maz['web_share']:.2%}**.",
        f"- Email ponderado en último corte: **{last_maz['email_share']:.2%}**.",
        "",
        f"### Principales sectores de Mazatlán · {latest_edition}",
        "",
        "| Sector | Establecimientos | Participación |",
        "|---|---:|---:|",
    ]
    for _, row in latest_sectors.iterrows():
        lines.append(f"| {row['sector']} | {int(row['establishments']):,} | {row['share']:.2%} |")

    lines += [
        "",
        "## Calidad del último corte",
        "",
        f"- Sin AGEB: **{quality['missing_ageb_share']:.4%}**.",
        f"- Sin cuadrícula: **{quality['missing_grid_share']:.4%}**.",
        f"- Sin código postal: **{quality['missing_postal_share']:.2%}**.",
        f"- CP con prefijo fuera de la heurística Sinaloa 80/81/82: **{quality['postal_prefix_outlier_share']:.2%}**.",
        "",
        "## Saltos de al menos 5% entre cortes",
        "",
        "| Edición | Cambio | Rebenchmark |",
        "|---|---:|:---:|",
    ]
    for _, row in jumps.iterrows():
        lines.append(f"| {row['source_edition']} | {row['growth_pct']:.2f}% | {'sí' if row['rebenchmark'] else 'no'} |")

    model_summary_path = args.models / "model_summary.json"
    if model_summary_path.exists():
        summary = json.loads(model_summary_path.read_text(encoding="utf-8"))
        spatial = summary.get("spatial_cv_mean", {})
        temporal = summary.get("temporal_holdout_mean", {})
        lines += [
            "",
            "## Validación predictiva",
            "",
            "Los modelos de dinámica son exploratorios/predictivos, no causales.",
            "",
            f"- MAE espacial RF: **{spatial.get('mae_stock', float('nan')):.3f}** vs persistencia **{spatial.get('baseline_mae_stock', float('nan')):.3f}**.",
            f"- RMSE espacial RF: **{spatial.get('rmse_stock', float('nan')):.3f}** vs persistencia **{spatial.get('baseline_rmse_stock', float('nan')):.3f}**.",
            f"- MAE temporal RF: **{temporal.get('mae_stock', float('nan')):.3f}** vs persistencia **{temporal.get('baseline_mae_stock', float('nan')):.3f}**.",
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
