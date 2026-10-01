from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS
from statsmodels.stats.diagnostic import het_breuschpagan, het_white
from statsmodels.stats.outliers_influence import variance_inflation_factor


@dataclass(slots=True)
class RegressionResult:
    model_family: str
    nobs: int
    coefficients: pd.DataFrame
    diagnostics: dict[str, float | int | str | None]
    metrics: dict[str, float | int | None]


def _coefficient_frame(result) -> pd.DataFrame:
    conf = result.conf_int()
    return pd.DataFrame(
        {
            "term": result.params.index,
            "estimate": result.params.values,
            "std_error": result.bse.values,
            "statistic": result.tvalues.values,
            "p_value": result.pvalues.values,
            "conf_low": conf.iloc[:, 0].values,
            "conf_high": conf.iloc[:, 1].values,
        }
    )


def variance_inflation_factors(frame: pd.DataFrame, regressors: Iterable[str]) -> pd.DataFrame:
    x = frame[list(regressors)].dropna().astype(float)
    x = sm.add_constant(x, has_constant="add")
    return pd.DataFrame(
        {
            "term": x.columns,
            "vif": [variance_inflation_factor(x.values, i) for i in range(x.shape[1])],
        }
    )


def fit_ols(
    frame: pd.DataFrame,
    dependent: str,
    regressors: list[str],
    covariance: str = "HC3",
    hac_lags: int | None = None,
) -> RegressionResult:
    cols = [dependent, *regressors]
    sample = frame[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if sample.empty:
        raise ValueError("No complete observations available for OLS")

    y = sample[dependent].astype(float)
    x = sm.add_constant(sample[regressors].astype(float), has_constant="add")
    base = sm.OLS(y, x).fit()

    if covariance.upper() == "HAC":
        if hac_lags is None:
            hac_lags = max(1, int(np.floor(4 * (len(sample) / 100) ** (2 / 9))))
        result = base.get_robustcov_results(cov_type="HAC", maxlags=hac_lags)
        robust_method = f"HAC({hac_lags})"
    else:
        result = base.get_robustcov_results(cov_type=covariance.upper())
        robust_method = covariance.upper()

    # Robust results return arrays, so rebuild a named coefficient table.
    conf = result.conf_int()
    coefficients = pd.DataFrame(
        {
            "term": x.columns,
            "estimate": result.params,
            "std_error": result.bse,
            "statistic": result.tvalues,
            "p_value": result.pvalues,
            "conf_low": conf[:, 0],
            "conf_high": conf[:, 1],
            "robust_method": robust_method,
        }
    )

    resid = base.resid
    white_lm, white_p, _, _ = het_white(resid, x)
    bp_lm, bp_p, _, _ = het_breuschpagan(resid, x)

    return RegressionResult(
        model_family="OLS",
        nobs=int(base.nobs),
        coefficients=coefficients,
        diagnostics={
            "white_lm": float(white_lm),
            "white_p_value": float(white_p),
            "breusch_pagan_lm": float(bp_lm),
            "breusch_pagan_p_value": float(bp_p),
            "condition_number": float(base.condition_number),
        },
        metrics={
            "r_squared": float(base.rsquared),
            "adj_r_squared": float(base.rsquared_adj),
            "aic": float(base.aic),
            "bic": float(base.bic),
            "rmse": float(np.sqrt(np.mean(np.square(resid)))),
        },
    )


def fit_panel_fixed_effects(
    frame: pd.DataFrame,
    entity: str,
    time: str,
    dependent: str,
    regressors: list[str],
    entity_effects: bool = True,
    time_effects: bool = True,
) -> RegressionResult:
    cols = [entity, time, dependent, *regressors]
    sample = frame[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if sample.empty:
        raise ValueError("No complete observations available for panel estimation")

    sample = sample.set_index([entity, time]).sort_index()
    y = sample[dependent].astype(float)
    x = sample[regressors].astype(float)

    model = PanelOLS(
        y,
        x,
        entity_effects=entity_effects,
        time_effects=time_effects,
        drop_absorbed=True,
        check_rank=True,
    )
    result = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    conf = result.conf_int()
    coefficients = pd.DataFrame(
        {
            "term": result.params.index,
            "estimate": result.params.values,
            "std_error": result.std_errors.values,
            "statistic": result.tstats.values,
            "p_value": result.pvalues.values,
            "conf_low": conf.iloc[:, 0].values,
            "conf_high": conf.iloc[:, 1].values,
            "robust_method": "two-way clustered",
        }
    )

    return RegressionResult(
        model_family="PanelFE",
        nobs=int(result.nobs),
        coefficients=coefficients,
        diagnostics={
            "entity_effects": int(entity_effects),
            "time_effects": int(time_effects),
        },
        metrics={
            "r_squared_within": float(result.rsquared_within),
            "r_squared_between": float(result.rsquared_between),
            "r_squared_overall": float(result.rsquared_overall),
        },
    )
