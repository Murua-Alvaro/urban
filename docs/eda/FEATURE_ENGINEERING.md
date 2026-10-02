# Feature engineering for econometrics

The feature store is built after cleaning and spatial EDA. It adds lagged/lead establishment stock, log stock and log changes, continuity growth excluding known rebenchmark transitions, time since first activity, regime indicators, active-history share, sector diversity/concentration, digital-contact shares, size-band shares, long-form sector location quotients and Queen-neighbor stock features for grids.

`model_transition_ok` is a conservative default sample flag: a transition must have a prior observation and must not terminate at a known full rebenchmark edition. It does not make a causal claim; it only prevents obvious measurement-regime transitions from silently entering baseline longitudinal models.
