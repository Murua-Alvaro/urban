# DENUE notebooks

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Murua-Alvaro/urban/blob/feat/denue-colab-workspace/notebooks/denue/00_COLAB_START_HERE.ipynb)

## START HERE — Google Colab

Use `00_COLAB_START_HERE.ipynb` as the main entrypoint. It clones the correct GitHub branch, installs the Colab environment, configures local or Google Drive cache, and runs the DENUE pipeline by stage.

Once `Growa_DENUE_Sinaloa_Historico_2010_2026.zip` is stored in `data/denue/raw/` on the `data/denue-historico` branch, Colab downloads and verifies it automatically. It is not necessary to upload the ZIP manually on every runtime.

Available stages:

- `load` — archive acquisition, checksum and safe extraction.
- `validate` — schema, totals, grouped keys and quality gates.
- `clean` — canonical typed Parquet staging.
- `eda` — statewide/municipal longitudinal EDA.
- `spatial` — AGEB/grid spatial EDA and territorial concentration.
- `features` — econometric-ready territorial feature store.
- `all` — full reproducible analytical pipeline.

Set `USE_DRIVE_CACHE = True` in the notebook to persist the verified ZIP and analytical outputs between Colab sessions.

## Modular notebooks

Notebooks are thin clients over tested package code; analytical logic belongs in `src/urban_denue`, not hidden inside notebook cells.

Suggested sequence:

- `00_COLAB_START_HERE.ipynb` — recommended Colab entrypoint.
- `00_colab_bootstrap.ipynb` — legacy/bootstrap helper.
- `10_load_validate.ipynb` — download, checksum, extraction and validation.
- `20_clean_core_eda.ipynb` — canonical Parquet staging and longitudinal EDA.
- `30_spatial_features.ipynb` — spatial EDA and econometric feature store.
- `50_modeling.ipynb` — leakage-aware econometric/predictive modeling.

For a fully automated terminal run use `make denue-full`.
