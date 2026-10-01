import numpy as np
import pandas as pd

from urban_analytics.econometrics import fit_ols, variance_inflation_factors


def test_ols_recovers_known_signal():
    rng = np.random.default_rng(20261001)
    n = 800
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 1.5 + 2.0 * x1 - 0.7 * x2 + rng.normal(scale=0.35, size=n)
    frame = pd.DataFrame({"y": y, "x1": x1, "x2": x2})

    result = fit_ols(frame, "y", ["x1", "x2"], covariance="HC3")
    beta = result.coefficients.set_index("term")["estimate"]

    assert result.nobs == n
    assert abs(beta["x1"] - 2.0) < 0.08
    assert abs(beta["x2"] + 0.7) < 0.08
    assert result.metrics["r_squared"] > 0.9


def test_vif_returns_named_terms():
    frame = pd.DataFrame({"x1": [1, 2, 3, 4, 5], "x2": [5, 4, 2, 1, 0]})
    vif = variance_inflation_factors(frame, ["x1", "x2"])
    assert {"const", "x1", "x2"}.issubset(set(vif["term"]))
