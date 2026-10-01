from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold


@dataclass(slots=True)
class FoldMetric:
    fold: int
    n_train: int
    n_test: int
    mae: float
    rmse: float
    r2: float


def grouped_random_forest_validation(
    frame: pd.DataFrame,
    dependent: str,
    features: list[str],
    group: str,
    n_splits: int = 5,
    random_seed: int = 20261001,
) -> pd.DataFrame:
    """Out-of-group validation to reduce spatial leakage.

    `group` should represent a geography unit (for example AGEB, neighborhood,
    municipality, or city). This is intentionally preferable to random row
    splitting when nearby observations share local shocks and amenities.
    """
    sample = frame[[dependent, group, *features]].replace([np.inf, -np.inf], np.nan).dropna()
    if sample[group].nunique() < n_splits:
        raise ValueError("Not enough unique groups for requested cross-validation folds")

    splitter = GroupKFold(n_splits=n_splits)
    x = sample[features].astype(float)
    y = sample[dependent].astype(float)
    groups = sample[group]
    rows: list[FoldMetric] = []

    for fold, (train_idx, test_idx) in enumerate(splitter.split(x, y, groups), start=1):
        model = RandomForestRegressor(
            n_estimators=500,
            min_samples_leaf=5,
            max_features="sqrt",
            random_state=random_seed + fold,
            n_jobs=-1,
        )
        model.fit(x.iloc[train_idx], y.iloc[train_idx])
        pred = model.predict(x.iloc[test_idx])
        truth = y.iloc[test_idx]
        rows.append(
            FoldMetric(
                fold=fold,
                n_train=len(train_idx),
                n_test=len(test_idx),
                mae=float(mean_absolute_error(truth, pred)),
                rmse=float(np.sqrt(mean_squared_error(truth, pred))),
                r2=float(r2_score(truth, pred)),
            )
        )

    return pd.DataFrame([asdict(metric) for metric in rows])
