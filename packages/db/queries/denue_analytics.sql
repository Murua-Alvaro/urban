-- Reusable DENUE analytical queries.
-- Replace bind placeholders (:...) in the application layer.

-- 1) Historical stock for one municipality.
-- Example :municipality_code = '25_012'.
SELECT
    e.source_edition,
    e.edition_date,
    e.is_rebenchmark,
    SUM(o.establishments)::bigint AS establishments
FROM denue_observations o
JOIN denue_editions e USING (source_edition)
WHERE o.municipality_code = :municipality_code
GROUP BY e.source_edition, e.edition_date, e.is_rebenchmark
ORDER BY e.edition_date;

-- 2) Grid stock and diversity proxy for a selected edition/municipality.
SELECT
    o.grid_id,
    SUM(o.establishments)::bigint AS establishments,
    COUNT(DISTINCT o.sector) AS sectors,
    COUNT(DISTINCT o.scian6) AS scian6_classes,
    g.centroid,
    g.area_m2
FROM denue_observations o
LEFT JOIN denue_grid_geometries g
  ON g.municipality_code = o.municipality_code
 AND g.grid_id = o.grid_id
WHERE o.source_edition = :source_edition
  AND o.municipality_code = :municipality_code
  AND NOT o.missing_grid
GROUP BY o.grid_id, g.centroid, g.area_m2;

-- 3) Municipality-relative sector LQ by grid.
WITH grid_sector AS (
    SELECT source_edition, municipality_code, grid_id, sector,
           SUM(establishments)::double precision AS n
    FROM denue_observations
    WHERE source_edition = :source_edition
      AND municipality_code = :municipality_code
      AND NOT missing_grid
    GROUP BY source_edition, municipality_code, grid_id, sector
),
grid_total AS (
    SELECT source_edition, municipality_code, grid_id, SUM(n) AS n
    FROM grid_sector
    GROUP BY source_edition, municipality_code, grid_id
),
mun_sector AS (
    SELECT source_edition, municipality_code, sector, SUM(n) AS n
    FROM grid_sector
    GROUP BY source_edition, municipality_code, sector
),
mun_total AS (
    SELECT source_edition, municipality_code, SUM(n) AS n
    FROM mun_sector
    GROUP BY source_edition, municipality_code
)
SELECT
    gs.grid_id,
    gs.sector,
    gs.n AS sector_establishments,
    gs.n / NULLIF(gt.n, 0) AS grid_share,
    ms.n / NULLIF(mt.n, 0) AS municipality_share,
    (gs.n / NULLIF(gt.n, 0)) / NULLIF(ms.n / NULLIF(mt.n, 0), 0) AS lq_municipality
FROM grid_sector gs
JOIN grid_total gt USING (source_edition, municipality_code, grid_id)
JOIN mun_sector ms USING (source_edition, municipality_code, sector)
JOIN mun_total mt USING (source_edition, municipality_code)
ORDER BY lq_municipality DESC NULLS LAST;

-- 4) Weighted contact/digital presence by municipality and edition.
SELECT
    o.source_edition,
    e.edition_date,
    o.municipality_code,
    SUM(o.establishments) AS establishments,
    SUM(o.establishments) FILTER (WHERE o.has_phone)::double precision / NULLIF(SUM(o.establishments), 0) AS phone_share,
    SUM(o.establishments) FILTER (WHERE o.has_email)::double precision / NULLIF(SUM(o.establishments), 0) AS email_share,
    SUM(o.establishments) FILTER (WHERE o.has_web)::double precision / NULLIF(SUM(o.establishments), 0) AS web_share
FROM denue_observations o
JOIN denue_editions e USING (source_edition)
WHERE o.municipality_code = :municipality_code
GROUP BY o.source_edition, e.edition_date, o.municipality_code
ORDER BY e.edition_date;

-- 5) Data quality by edition. Shares are establishment-weighted.
SELECT
    o.source_edition,
    e.edition_date,
    SUM(o.establishments) AS establishments,
    SUM(o.establishments) FILTER (WHERE o.missing_ageb)::double precision / NULLIF(SUM(o.establishments), 0) AS missing_ageb_share,
    SUM(o.establishments) FILTER (WHERE o.missing_grid)::double precision / NULLIF(SUM(o.establishments), 0) AS missing_grid_share,
    SUM(o.establishments) FILTER (WHERE o.missing_postal_code)::double precision / NULLIF(SUM(o.establishments), 0) AS missing_postal_share
FROM denue_observations o
JOIN denue_editions e USING (source_edition)
GROUP BY o.source_edition, e.edition_date
ORDER BY e.edition_date;

-- 6) Grid stock transition table using actual edition ordering.
WITH grid_stock AS (
    SELECT
        o.municipality_code,
        o.grid_id,
        e.edition_date,
        e.source_edition,
        e.is_rebenchmark,
        SUM(o.establishments)::bigint AS establishments
    FROM denue_observations o
    JOIN denue_editions e USING (source_edition)
    WHERE NOT o.missing_grid
      AND o.municipality_code = :municipality_code
    GROUP BY o.municipality_code, o.grid_id, e.edition_date, e.source_edition, e.is_rebenchmark
),
with_lags AS (
    SELECT *,
        LAG(establishments) OVER (PARTITION BY municipality_code, grid_id ORDER BY edition_date) AS previous_establishments,
        LAG(edition_date) OVER (PARTITION BY municipality_code, grid_id ORDER BY edition_date) AS previous_date
    FROM grid_stock
)
SELECT *,
    establishments - previous_establishments AS stock_change,
    CASE
        WHEN previous_establishments > 0 THEN 100.0 * (establishments::double precision / previous_establishments - 1.0)
        ELSE NULL
    END AS growth_pct
FROM with_lags
ORDER BY grid_id, edition_date;
