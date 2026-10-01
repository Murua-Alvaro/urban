from __future__ import annotations

import numpy as np
import pandas as pd


def prepare_hedonic_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Create transparent hedonic features without silently deleting observations."""
    data = frame.copy()

    for column in ("price", "area_built_m2", "area_land_m2", "bedrooms", "bathrooms"):
        if column in data:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    built = data.get("area_built_m2", pd.Series(np.nan, index=data.index, dtype=float))
    land = data.get("area_land_m2", pd.Series(np.nan, index=data.index, dtype=float))
    denominator = built.where(built > 0, land.where(land > 0))
    data["price_area_basis"] = np.where(built > 0, "built_m2", np.where(land > 0, "land_m2", None))
    data["listing_price_m2"] = data.get("price", np.nan) / denominator

    positive_price = data["listing_price_m2"] > 0
    data["log_listing_price_m2"] = np.where(positive_price, np.log(data["listing_price_m2"]), np.nan)

    if "area_built_m2" in data:
        data["log_area_built_m2"] = np.where(data["area_built_m2"] > 0, np.log(data["area_built_m2"]), np.nan)
    if "area_land_m2" in data:
        data["log_area_land_m2"] = np.where(data["area_land_m2"] > 0, np.log(data["area_land_m2"]), np.nan)

    valid = data["listing_price_m2"].dropna()
    if len(valid) >= 20:
        q_low, q_high = valid.quantile([0.01, 0.99])
        data["price_m2_outlier_1pct"] = (data["listing_price_m2"] < q_low) | (data["listing_price_m2"] > q_high)
    else:
        data["price_m2_outlier_1pct"] = False

    if "observed_at" in data:
        observed = pd.to_datetime(data["observed_at"], errors="coerce")
        data["period_month"] = observed.dt.to_period("M").astype("string")

    return data
