# Econometric methodology

## Objective

Urban separates descriptive urban intelligence, predictive modeling, and causal inference. A high out-of-sample score is not treated as evidence of a causal effect.

## Model ladder

1. **Descriptive diagnostics**: distributions, missingness, duplicate listings, price-per-m2 outliers, spatial coverage, temporal coverage and source consistency.
2. **Hedonic OLS baseline**: log price per m2 on structural property controls, accessibility, density and local economic composition. Report HC3 or HAC covariance as appropriate.
3. **Panel fixed effects**: geography and period effects when repeated observations permit within-area identification. Standard errors are clustered by geography and time.
4. **Spatial diagnostics**: Moran's I on baseline residuals. Spatial models are only introduced when residual dependence and the research question justify them.
5. **Spatial lag / error specifications**: KNN and contiguity weights are treated as model choices and subjected to sensitivity analysis rather than selected post hoc from one favorable result.
6. **Predictive benchmark**: Random Forest and later gradient boosting are validated with geographic groups to reduce leakage from nearby observations.

## Reproducibility rules

Every model run should persist: dataset SHA-256, sample definition, dependent variable, regressors, transformations, fixed effects, spatial-weight specification, robust covariance method, random seed, code version, diagnostics, metrics and coefficient table.

## Data transformations

- Prices are preserved in nominal values and may additionally be deflated when a defensible price index is available.
- `price_m2` must record whether land or built area is used as denominator.
- Log transforms use strictly positive observations; dropped observations are counted and stored.
- Coordinates are validated against plausible bounds before spatial joins.
- Duplicated listings should be identified using source ID when available and otherwise by a documented composite/fuzzy rule.

## Validation

Random row splits are not the default for spatial observations. Validation should use AGEB, neighborhood, municipality or city groups depending on the prediction target. For multi-city work, leave-one-city-out validation is preferred as an external-validity check.

## Inference safeguards

- Heteroskedasticity: White and Breusch-Pagan diagnostics; robust covariance by default.
- Multicollinearity: VIF plus stability across nested specifications; VIF is diagnostic, not an automatic variable-deletion rule.
- Spatial dependence: Moran residual diagnostic before interpreting conventional standard errors as sufficient.
- Multiple testing: families of exploratory hypotheses should use FDR or a resampling-based family-wise procedure when the number of tests becomes material.
- Causal language requires an explicit identification design (for example event study, difference-in-differences, IV, RDD or a defensible natural experiment). Ordinary hedonic associations are reported as associations.
