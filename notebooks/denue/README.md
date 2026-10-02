# DENUE notebooks

Notebooks are thin clients over tested package code; analytical logic belongs in `src/urban_denue`, not hidden inside notebook cells.

Suggested sequence:

- `00_colab_bootstrap.ipynb` — legacy/bootstrap helper.
- `10_load_validate.ipynb` — download, checksum, extraction and validation.
- `20_clean_core_eda.ipynb` — canonical Parquet staging and longitudinal EDA.
- `30_spatial_features.ipynb` — spatial EDA and econometric feature store.

For a fully automated run use `python scripts/denue/run_pipeline.py --through all`.
