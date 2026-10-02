# Exploratory and predictive modeling

The modeling layer is downstream of the validated, cleaned and spatially balanced feature store. It does **not** claim causal effects.

Baseline specifications:

- OLS on next-edition log stock with HC3 covariance.
- Poisson QMLE on next-edition establishment stock with HC3 covariance.
- Random Forest evaluated with `GroupKFold` where the entire municipality-grid identity stays in one fold, preventing same-grid leakage.
- Rolling temporal holdouts for the latest target editions.
- Persistence (`next stock = current stock`) as the minimum predictive baseline.

Transitions whose **target** edition is a full DENUE rebenchmark (2015-01, 2019-11, 2024-11) are excluded from the primary model sample. Model outputs record absolute error as well as improvement or deterioration versus persistence.

The panel never backfills municipalities before they appear as separate DENUE units. This matters especially for Eldorado and Juan José Ríos, which should not receive synthetic pre-2025 zero histories.
