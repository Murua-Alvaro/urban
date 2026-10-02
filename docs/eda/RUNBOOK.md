# DENUE EDA runbook

## GitHub Codespaces

Open a Codespace on `feat/denue-eda-pipeline`. The devcontainer installs Python 3.11 and the project automatically. Run `make test`, then `make denue-all`.

## Google Colab

Clone the repository/branch once per ephemeral Colab runtime, install the package, and execute the pipeline. The raw ZIP is downloaded automatically from `data/denue-historico`, verified by size and SHA-256, then cached for the rest of the runtime. No manual file upload is required after the archive exists on GitHub.

## GitHub Actions

`DENUE Full Pipeline` can be run manually. It executes tests, downloads/verifies the archive, runs all stages and uploads compact reports/features as a temporary Actions artifact. Heavy generated files are not committed.

## Stage contract

`load -> validate -> clean -> eda -> spatial -> features`

A stage never mutates raw data. Validation errors stop the run. Rebenchmark transitions remain explicit. The pipeline manifest records source checksum, environment versions, stage outputs and row counts.
