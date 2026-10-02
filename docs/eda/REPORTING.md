# Automated EDA reporting

Reporting is deliberately downstream of the reproducible Parquet artifacts. It does not recalculate raw indicators inside charts. State and municipality reports summarize the historical stock, sector structure and grid concentration, mark the methodological limits of inter-edition changes and save figures plus Markdown under `var/denue/reports/`.

Example:

```bash
python scripts/denue/report.py --municipality 012
```

Municipality `012` is Mazatlán. Other municipality codes can be generated with the same command once the pipeline has produced the EDA artifacts.
