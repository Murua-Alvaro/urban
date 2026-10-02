# Cleaning and canonicalization

Cleaning never overwrites raw values. Source edition labels are retained and a separate canonical label/date is added. In particular, source label `2015-02` is mapped to official analysis edition `2015-01`; `2013-A/B` become `2013-07/2013-10`.

Missing AGEB/grid and suspicious postal codes are represented with analysis columns rather than row deletion. Contact flags are decoded into phone/email/web booleans. Clean outputs are immutable Parquet partitions under `staged/edition=...`.
