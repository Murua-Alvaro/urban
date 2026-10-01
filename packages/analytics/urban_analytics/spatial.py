from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
from esda.moran import Moran
from libpysal.weights import KNN, Queen
from spreg import ML_Lag


@dataclass(slots=True)
class MoranDiagnostic:
    statistic: float
    expected: float
    p_value_sim: float
    z_score_sim: float


@dataclass(slots=True)
class SpatialLagResult:
    coefficients: pd.DataFrame
    diagnostics: dict[str, float | int]
    metrics: dict[str, float | int]


def build_weights(
    frame: gpd.GeoDataFrame,
    method: str = "knn",
    k: int = 8,
    row_standardize: bool = True,
):
    if frame.crs is None:
        raise ValueError("GeoDataFrame requires a CRS before spatial weights can be built")
    if method == "queen":
        weights = Queen.from_dataframe(frame, use_index=False)
    elif method == "knn":
        working = frame.copy()
        if working.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
            working["geometry"] = working.geometry.centroid
        weights = KNN.from_dataframe(working, k=k, use_index=False)
    else:
        raise ValueError(f"Unsupported weights method: {method}")

    if row_standardize:
        weights.transform = "r"
    return weights


def moran_residual_test(residuals: np.ndarray | pd.Series, weights, permutations: int = 999) -> MoranDiagnostic:
    test = Moran(np.asarray(residuals, dtype=float), weights, permutations=permutations)
    return MoranDiagnostic(
        statistic=float(test.I),
        expected=float(test.EI),
        p_value_sim=float(test.p_sim),
        z_score_sim=float(test.z_sim),
    )


def fit_spatial_lag(
    frame: gpd.GeoDataFrame,
    dependent: str,
    regressors: list[str],
    weights_method: str = "knn",
    k: int = 8,
) -> SpatialLagResult:
    cols = [dependent, *regressors, frame.geometry.name]
    sample = frame[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if len(sample) <= max(k + 1, len(regressors) + 3):
        raise ValueError("Insufficient complete observations for spatial lag estimation")

    weights = build_weights(sample, method=weights_method, k=k)
    y = sample[[dependent]].astype(float).to_numpy()
    x = sample[regressors].astype(float).to_numpy()
    model = ML_Lag(y, x, w=weights, name_y=dependent, name_x=regressors, method="full")

    names = ["constant", *regressors, "W_dependent"]
    betas = model.betas.flatten()
    std_err = np.asarray(model.std_err).flatten()
    zstats = list(model.z_stat)
    coefficients = pd.DataFrame(
        {
            "term": names[: len(betas)],
            "estimate": betas,
            "std_error": std_err,
            "statistic": [float(z[0]) for z in zstats],
            "p_value": [float(z[1]) for z in zstats],
        }
    )

    residual_moran = moran_residual_test(model.u.flatten(), weights)
    return SpatialLagResult(
        coefficients=coefficients,
        diagnostics={
            "moran_residual_i": residual_moran.statistic,
            "moran_residual_p": residual_moran.p_value_sim,
            "weights_k": k,
        },
        metrics={
            "nobs": int(model.n),
            "log_likelihood": float(model.logll),
            "aic": float(model.aic),
            "schwarz": float(model.schwarz),
            "pseudo_r2": float(model.pr2),
        },
    )
