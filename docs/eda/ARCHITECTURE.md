# DENUE historical EDA architecture

The DENUE workflow is split into stacked branches so each concern can be reviewed independently.

1. `feat/denue-env` — reproducible Python, Colab and GitHub Actions environment.
2. `feat/denue-loader` — immutable archive acquisition, checksum verification, safe extraction and catalog loading.
3. `feat/denue-validation` — schema, totals, keys, geography and quality assertions.
4. `feat/denue-cleaning` — canonical editions, dtypes, missing-value flags and geography quality rules.
5. `feat/denue-eda-core` — state, municipality, SCIAN, size and time EDA plus regime-break diagnostics.
6. `feat/denue-spatial-eda` — AGEB/grid concentration, diversity, entry/exit proxies and spatial summaries.
7. `feat/denue-eda-pipeline` — end-to-end CLI/notebook orchestration and artifact registry.

The raw ZIP is immutable input. Every downstream artifact must be reproducible from the checksum-verified archive. Generated data are written under `var/denue/` and are not committed by default.
