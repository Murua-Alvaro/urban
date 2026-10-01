from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import pandas as pd
from sqlalchemy import create_engine, text

from .econometrics import fit_ols


@dataclass(slots=True)
class OLSRunSpec:
    specification_name: str
    dependent: str
    regressors: list[str]
    covariance: str = "HC3"
    hac_lags: int | None = None
    random_seed: int = 20261001


def run_ols_and_persist(
    database_url: str,
    dataset_id: str,
    frame: pd.DataFrame,
    spec: OLSRunSpec,
    code_version: str | None = None,
) -> str:
    result = fit_ols(
        frame=frame,
        dependent=spec.dependent,
        regressors=spec.regressors,
        covariance=spec.covariance,
        hac_lags=spec.hac_lags,
    )

    sample_cols = [spec.dependent, *spec.regressors]
    n_complete = int(frame[sample_cols].dropna().shape[0])
    sample_definition = {
        "n_input": int(len(frame)),
        "n_complete": n_complete,
        "dependent": spec.dependent,
        "regressors": spec.regressors,
        "drop_missing": "complete_case",
    }

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO model_runs(
                    dataset_id, model_family, specification_name, dependent_variable,
                    formula, sample_definition, diagnostics, metrics, code_version,
                    random_seed, completed_at
                ) VALUES (
                    CAST(:dataset_id AS uuid), 'OLS', :specification_name, :dependent,
                    :formula, CAST(:sample_definition AS jsonb), CAST(:diagnostics AS jsonb),
                    CAST(:metrics AS jsonb), :code_version, :random_seed, now()
                )
                RETURNING id
                """
            ),
            {
                "dataset_id": dataset_id,
                "specification_name": spec.specification_name,
                "dependent": spec.dependent,
                "formula": f"{spec.dependent} ~ {' + '.join(spec.regressors)}",
                "sample_definition": json.dumps(sample_definition),
                "diagnostics": json.dumps(result.diagnostics),
                "metrics": json.dumps(result.metrics),
                "code_version": code_version,
                "random_seed": spec.random_seed,
            },
        ).mappings().one()
        model_run_id = str(row["id"])

        coefficients = result.coefficients.copy()
        coefficient_rows = []
        for record in coefficients.to_dict(orient="records"):
            coefficient_rows.append(
                {
                    "model_run_id": model_run_id,
                    "term": record.get("term"),
                    "estimate": record.get("estimate"),
                    "std_error": record.get("std_error"),
                    "statistic": record.get("statistic"),
                    "p_value": record.get("p_value"),
                    "conf_low": record.get("conf_low"),
                    "conf_high": record.get("conf_high"),
                    "robust_method": record.get("robust_method", spec.covariance),
                }
            )

        conn.execute(
            text(
                """
                INSERT INTO model_coefficients(
                    model_run_id, term, estimate, std_error, statistic, p_value,
                    conf_low, conf_high, robust_method
                ) VALUES (
                    CAST(:model_run_id AS uuid), :term, :estimate, :std_error, :statistic,
                    :p_value, :conf_low, :conf_high, :robust_method
                )
                """
            ),
            coefficient_rows,
        )

    engine.dispose()
    return model_run_id
