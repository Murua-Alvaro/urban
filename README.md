# Urban

Urban is a reproducible urban data science and econometrics platform for ingesting real-estate and territorial datasets, validating them, persisting structured observations, and estimating spatial/econometric models.

## Architecture

- `apps/web`: web interface for ZIP upload, data catalog, diagnostics and model results.
- `services/api`: FastAPI service for ingestion, validation, persistence and analytics.
- `packages/db`: PostgreSQL/PostGIS schema and seed data.
- `packages/analytics`: econometrics and spatial data-science modules.
- `docs`: methodology, data contracts and architecture decisions.

## Branch strategy

- `feat/data-ingestion`: ZIP ingestion, validation, manifests and persistence pipeline.
- `feat/database-seed`: PostgreSQL/PostGIS schema, migrations and reproducible seed.
- `feat/econometrics`: econometric and spatial-modeling core.
- `feat/web-urban-lab`: upload/data/model UI.

The repository starts intentionally small on `main`; feature work is developed in isolated branches and integrated through pull requests.
