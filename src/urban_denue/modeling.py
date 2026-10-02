from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

NUMERIC_FEATURES = [
    "log_stock", "effective_sectors", "sector_hhi", "sectors", "scian6_classes",
    "phone_share", "email_share", "web_share", "active_share_history",
    "neighbor_stock_mean", "relative_to_neighbor_mean",
]
CATEGORICAL_FEATURES = ["municipality_code", "canonical_edition"]


def prepare_grid_model_sample(features: pd.DataFrame) -> pd.DataFrame:
    df = features.copy()
    df["edition_date"] = pd.to_datetime(df["edition_date"])
    df = df.sort_values(["municipality_key", "grid_analysis", "edition_date"]).reset_index(drop=True)
    group = df.groupby(["municipality_key", "grid_analysis"], group_keys=False)
    df["next_date"] = group["edition_date"].shift(-1)
    df["next_rebenchmark"] = group["rebenchmark"].shift(-1).fillna(False).astype(bool)
    df["target_stock"] = group["establishments"].shift(-1)
    df["target_log_stock"] = np.log1p(df["target_stock"])
    df["geo_id"] = df["municipality_key"].astype(str) + "|" + df["grid_analysis"].astype(str)
    sample = df.loc[df["target_stock"].notna() & ~df["next_rebenchmark"]].copy()
    for col in NUMERIC_FEATURES:
        if col not in sample:
            sample[col] = 0.0
        sample[col] = pd.to_numeric(sample[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    sample["target_stock"] = pd.to_numeric(sample["target_stock"], errors="raise")
    sample["target_log_stock"] = np.log1p(sample["target_stock"])
    return sample


def _formula(target: str) -> str:
    numeric = " + ".join(NUMERIC_FEATURES)
    return f"{target} ~ {numeric} + C(municipality_code) + C(canonical_edition)"


def fit_ols_hc3(sample: pd.DataFrame):
    return smf.ols(_formula("target_log_stock"), data=sample).fit(cov_type="HC3")


def fit_poisson_qmle(sample: pd.DataFrame):
    return smf.glm(_formula("target_stock"), data=sample, family=sm.families.Poisson()).fit(cov_type="HC3")


def coefficient_frame(model) -> pd.DataFrame:
    ci = model.conf_int()
    return pd.DataFrame({
        "term": model.params.index,
        "estimate": model.params.to_numpy(),
        "std_error": model.bse.to_numpy(),
        "statistic": model.tvalues.to_numpy(),
        "p_value": model.pvalues.to_numpy(),
        "conf_low": ci.iloc[:, 0].to_numpy(),
        "conf_high": ci.iloc[:, 1].to_numpy(),
    })


def make_random_forest(seed: int = 20261002) -> Pipeline:
    pre = ColumnTransformer([
        ("numeric", "passthrough", NUMERIC_FEATURES),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
    ])
    rf = RandomForestRegressor(
        n_estimators=500, min_samples_leaf=5, max_features="sqrt",
        random_state=seed, n_jobs=-1,
    )
    return Pipeline([("pre", pre), ("model", rf)])


def _metrics(sample: pd.DataFrame, pred_log: np.ndarray, validation: str, fold: int | None = None) -> dict:
    true_stock = sample["target_stock"].to_numpy(dtype=float)
    pred_stock = np.expm1(pred_log).clip(min=0)
    baseline = sample["establishments"].to_numpy(dtype=float)
    mae = float(mean_absolute_error(true_stock, pred_stock))
    rmse = float(mean_squared_error(true_stock, pred_stock) ** 0.5)
    baseline_mae = float(mean_absolute_error(true_stock, baseline))
    baseline_rmse = float(mean_squared_error(true_stock, baseline) ** 0.5)
    return {
        "validation": validation, "fold": fold, "n": int(len(sample)),
        "mae_stock": mae, "rmse_stock": rmse,
        "r2_log": float(r2_score(sample["target_log_stock"], pred_log)),
        "baseline_mae_stock": baseline_mae, "baseline_rmse_stock": baseline_rmse,
        "mae_improvement_pct_vs_persistence": float((baseline_mae - mae) / baseline_mae * 100) if baseline_mae > 0 else np.nan,
        "rmse_improvement_pct_vs_persistence": float((baseline_rmse - rmse) / baseline_rmse * 100) if baseline_rmse > 0 else np.nan,
    }


def spatial_group_cv(sample: pd.DataFrame, folds: int = 5) -> pd.DataFrame:
    n_groups = sample["geo_id"].nunique()
    if n_groups < 2:
        return pd.DataFrame()
    n_splits = min(folds, n_groups)
    splitter = GroupKFold(n_splits=n_splits)
    X = sample[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = sample["target_log_stock"].to_numpy()
    groups = sample["geo_id"].to_numpy()
    rows = []
    for fold, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups), start=1):
        train_groups = set(groups[train_idx])
        test_groups = set(groups[test_idx])
        if train_groups & test_groups:
            raise RuntimeError("spatial GroupKFold leaked geography IDs")
        model = make_random_forest(20261002 + fold)
        model.fit(X.iloc[train_idx], y[train_idx])
        pred = model.predict(X.iloc[test_idx])
        rows.append(_metrics(sample.iloc[test_idx], pred, "spatial_group_kfold", fold))
    return pd.DataFrame(rows)


def rolling_temporal_holdouts(sample: pd.DataFrame, n_holdouts: int = 4) -> pd.DataFrame:
    target_dates = sorted(pd.to_datetime(sample["next_date"].dropna().unique()))[-n_holdouts:]
    rows = []
    for fold, target_date in enumerate(target_dates, start=1):
        train = sample.loc[sample["next_date"] < target_date].copy()
        test = sample.loc[sample["next_date"] == target_date].copy()
        if train.empty or test.empty:
            continue
        model = make_random_forest(20261100 + fold)
        model.fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train["target_log_stock"])
        pred = model.predict(test[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
        row = _metrics(test, pred, "rolling_temporal_holdout", fold)
        row["target_date"] = pd.Timestamp(target_date).date().isoformat()
        row["train_n"] = int(len(train))
        rows.append(row)
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class ModelArtifacts:
    sample: pd.DataFrame
    ols_coefficients: pd.DataFrame
    poisson_coefficients: pd.DataFrame
    spatial_cv: pd.DataFrame
    temporal_cv: pd.DataFrame
    diagnostics: dict


def run_models(features: pd.DataFrame) -> ModelArtifacts:
    sample = prepare_grid_model_sample(features)
    if sample.empty:
        raise ValueError("no valid next-edition grid transitions for modeling")
    ols = fit_ols_hc3(sample)
    poisson = fit_poisson_qmle(sample)
    spatial = spatial_group_cv(sample)
    temporal = rolling_temporal_holdouts(sample)
    diagnostics = {
        "purpose": "exploratory/predictive next-edition grid stock; not causal",
        "n": int(len(sample)), "geographies": int(sample["geo_id"].nunique()),
        "ols_adj_r2": float(ols.rsquared_adj), "ols_aic": float(ols.aic),
        "poisson_aic": float(poisson.aic), "poisson_deviance": float(poisson.deviance),
        "excluded_target_rebenchmarks": ["2015-01", "2019-11", "2024-11"],
        "spatial_cv_mean": spatial.mean(numeric_only=True).to_dict() if not spatial.empty else {},
        "temporal_cv_mean": temporal.mean(numeric_only=True).to_dict() if not temporal.empty else {},
    }
    return ModelArtifacts(sample, coefficient_frame(ols), coefficient_frame(poisson), spatial, temporal, diagnostics)


def write_models(artifacts: ModelArtifacts, output: Path) -> dict[str, str]:
    import json
    output.mkdir(parents=True, exist_ok=True)
    targets = {
        "sample": output / "model_sample.parquet",
        "ols": output / "ols_hc3_coefficients.csv",
        "poisson": output / "poisson_qmle_hc3_coefficients.csv",
        "spatial_cv": output / "rf_spatial_group_cv.csv",
        "temporal_cv": output / "rf_temporal_holdouts.csv",
        "summary": output / "model_summary.json",
    }
    artifacts.sample.to_parquet(targets["sample"], index=False)
    artifacts.ols_coefficients.to_csv(targets["ols"], index=False)
    artifacts.poisson_coefficients.to_csv(targets["poisson"], index=False)
    artifacts.spatial_cv.to_csv(targets["spatial_cv"], index=False)
    artifacts.temporal_cv.to_csv(targets["temporal_cv"], index=False)
    targets["summary"].write_text(json.dumps(artifacts.diagnostics, indent=2), encoding="utf-8")
    return {key: str(value) for key, value in targets.items()}
