from __future__ import annotations

import argparse
import json
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

REBENCHMARK_DATES = pd.to_datetime(["2015-01-01", "2019-11-01", "2024-11-01"])
NUMERIC_FEATURES = [
    "log1p_establishments",
    "effective_sectors",
    "sector_hhi",
    "sector_count",
    "scian6_count",
    "phone_share",
    "email_share",
    "web_share",
]
CATEGORICAL_FEATURES = ["municipality_code", "source_edition"]


def prepare_sample(features: pd.DataFrame, exclude_rebenchmark_targets: bool = True) -> pd.DataFrame:
    df = features.copy()
    df["edition_date"] = pd.to_datetime(df["edition_date"])
    df["next_date"] = pd.to_datetime(df["next_date"])
    df["next_rebenchmark"] = df["next_date"].isin(REBENCHMARK_DATES)
    df = df.loc[df["next_establishments"].notna()].copy()
    if exclude_rebenchmark_targets:
        df = df.loc[~df["next_rebenchmark"]].copy()
    for col in NUMERIC_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["next_establishments"] = pd.to_numeric(df["next_establishments"], errors="coerce")
    df["next_log1p_establishments"] = np.log1p(df["next_establishments"])
    return df


def fit_ols(sample: pd.DataFrame):
    formula = (
        "next_log1p_establishments ~ log1p_establishments + effective_sectors + sector_hhi + "
        "sector_count + scian6_count + phone_share + email_share + web_share + "
        "C(municipality_code) + C(source_edition)"
    )
    return smf.ols(formula, data=sample).fit(cov_type="HC3")


def fit_poisson(sample: pd.DataFrame):
    formula = (
        "next_establishments ~ log1p_establishments + effective_sectors + sector_hhi + "
        "sector_count + scian6_count + phone_share + email_share + web_share + "
        "C(municipality_code) + C(source_edition)"
    )
    return smf.glm(formula, data=sample, family=sm.families.Poisson()).fit(cov_type="HC3")


def coefficient_frame(model) -> pd.DataFrame:
    ci = model.conf_int()
    return pd.DataFrame(
        {
            "term": model.params.index,
            "estimate": model.params.values,
            "std_error": model.bse.values,
            "statistic": model.tvalues.values,
            "p_value": model.pvalues.values,
            "conf_low": ci.iloc[:, 0].values,
            "conf_high": ci.iloc[:, 1].values,
        }
    )


def make_rf(seed: int = 20261001) -> Pipeline:
    prep = ColumnTransformer(
        [
            ("numeric", "passthrough", NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )
    rf = RandomForestRegressor(
        n_estimators=500,
        min_samples_leaf=5,
        max_features="sqrt",
        n_jobs=-1,
        random_state=seed,
    )
    return Pipeline([("prep", prep), ("model", rf)])


def metric_row(y_true: np.ndarray, y_pred_log: np.ndarray, current_stock: np.ndarray, label: str, fold: int | None = None) -> dict:
    pred_stock = np.expm1(y_pred_log).clip(min=0)
    baseline_stock = current_stock
    return {
        "validation": label,
        "fold": fold,
        "n": int(len(y_true)),
        "mae_stock": float(mean_absolute_error(np.expm1(y_true), pred_stock)),
        "rmse_stock": float(mean_squared_error(np.expm1(y_true), pred_stock) ** 0.5),
        "r2_log": float(r2_score(y_true, y_pred_log)),
        "baseline_mae_stock": float(mean_absolute_error(np.expm1(y_true), baseline_stock)),
        "baseline_rmse_stock": float(mean_squared_error(np.expm1(y_true), baseline_stock) ** 0.5),
    }


def spatial_group_cv(sample: pd.DataFrame, folds: int = 5) -> pd.DataFrame:
    X = sample[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = sample["next_log1p_establishments"].to_numpy()
    groups = sample["geo_id"].astype(str).to_numpy()
    splitter = GroupKFold(n_splits=folds)
    rows: list[dict] = []
    for fold, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups), start=1):
        model = make_rf(seed=20261001 + fold)
        model.fit(X.iloc[train_idx], y[train_idx])
        pred = model.predict(X.iloc[test_idx])
        rows.append(
            metric_row(
                y[test_idx],
                pred,
                sample.iloc[test_idx]["establishments"].to_numpy(dtype=float),
                "spatial_group_kfold",
                fold,
            )
        )
    return pd.DataFrame(rows)


def temporal_holdouts(sample: pd.DataFrame, n_holdouts: int = 3) -> pd.DataFrame:
    target_dates = sorted(sample["next_date"].dropna().unique())[-n_holdouts:]
    rows: list[dict] = []
    for i, target_date in enumerate(target_dates, start=1):
        train = sample.loc[sample["next_date"] < target_date].copy()
        test = sample.loc[sample["next_date"] == target_date].copy()
        if train.empty or test.empty:
            continue
        model = make_rf(seed=20261100 + i)
        model.fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train["next_log1p_establishments"])
        pred = model.predict(test[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
        row = metric_row(
            test["next_log1p_establishments"].to_numpy(),
            pred,
            test["establishments"].to_numpy(dtype=float),
            "rolling_temporal_holdout",
            i,
        )
        row["target_date"] = pd.Timestamp(target_date).date().isoformat()
        row["train_n"] = int(len(train))
        rows.append(row)
    return pd.DataFrame(rows)


def model_diagnostics(model, family: str, sample_name: str, n: int) -> dict:
    result = {
        "family": family,
        "sample": sample_name,
        "n": int(n),
        "aic": float(model.aic),
    }
    if hasattr(model, "bic"):
        try:
            result["bic"] = float(model.bic)
        except Exception:
            pass
    if hasattr(model, "rsquared"):
        result["r2"] = float(model.rsquared)
        result["adj_r2"] = float(model.rsquared_adj)
    if hasattr(model, "deviance"):
        result["deviance"] = float(model.deviance)
        result["pearson_chi2"] = float(model.pearson_chi2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Exploratory econometric and ML models for DENUE grid stock dynamics.")
    parser.add_argument("--features", type=Path, default=Path("var/denue/analysis/grid_features.parquet"))
    parser.add_argument("--output", type=Path, default=Path("var/denue/models/grid_dynamics"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    features = pd.read_parquet(args.features)
    primary = prepare_sample(features, exclude_rebenchmark_targets=True)
    sensitivity = prepare_sample(features, exclude_rebenchmark_targets=False)

    diagnostics: list[dict] = []
    for name, sample in [("primary_excluding_rebenchmark_targets", primary), ("sensitivity_all_targets", sensitivity)]:
        ols = fit_ols(sample)
        coefficient_frame(ols).to_csv(args.output / f"ols_{name}_coefficients.csv", index=False)
        diagnostics.append(model_diagnostics(ols, "OLS_HC3_log_stock", name, len(sample)))

    poisson = fit_poisson(primary)
    coefficient_frame(poisson).to_csv(args.output / "poisson_primary_coefficients.csv", index=False)
    diagnostics.append(model_diagnostics(poisson, "Poisson_QMLE_HC3", "primary_excluding_rebenchmark_targets", len(primary)))

    spatial = spatial_group_cv(primary)
    temporal = temporal_holdouts(primary)
    spatial.to_csv(args.output / "rf_spatial_group_cv.csv", index=False)
    temporal.to_csv(args.output / "rf_temporal_holdouts.csv", index=False)

    summary = {
        "purpose": "Exploratory/predictive modeling of next-edition DENUE grid stock; not a causal estimate.",
        "target": "next edition establishments by municipality-grid",
        "primary_excludes_next_rebenchmark_dates": [d.date().isoformat() for d in REBENCHMARK_DATES],
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "diagnostics": diagnostics,
        "spatial_cv_mean": spatial.mean(numeric_only=True).to_dict(),
        "temporal_holdout_mean": temporal.mean(numeric_only=True).to_dict() if not temporal.empty else {},
    }
    (args.output / "model_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
