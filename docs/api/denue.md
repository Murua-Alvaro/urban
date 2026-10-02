# DENUE API

These endpoints read the canonical PostGIS tables introduced by the DENUE persistence migration.

## Editions

`GET /v1/denue/editions`

Returns the 25 canonical editions with analytical dates, rebenchmark flags and archive provenance.

## Data quality

`GET /v1/denue/quality`

Returns establishment-weighted missing shares for AGEB, grid and postal code by edition.

## Municipality time series

`GET /v1/denue/municipalities/25_012/timeseries`

Returns historical stock, active AGEB and active grids for Mazatlán. Municipality codes are validated as Sinaloa composite codes (`25_###`).

## Sector structure

`GET /v1/denue/municipalities/25_012/sectors?edition=2026-05&limit=30`

Returns sector establishments, municipality share, state share and state-relative location quotient.

## Grid map

`GET /v1/denue/municipalities/25_012/grids?edition=2026-05&min_establishments=1`

Returns a GeoJSON FeatureCollection containing grid geometry plus establishment stock, number of sectors/classes and weighted phone/email/web shares.

The API deliberately does not expose row-level business identities because the audited historical archive is an aggregated territorial derivative rather than establishment-level raw DENUE microdata.
