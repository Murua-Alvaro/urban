-- Historical DENUE derived territorial panel.
-- Stores the audited aggregated observations without pretending they are
-- establishment-level microdata.

CREATE TABLE IF NOT EXISTS denue_editions (
    source_edition text PRIMARY KEY,
    dataset_id uuid REFERENCES datasets(id) ON DELETE SET NULL,
    edition_date date NOT NULL,
    is_rebenchmark boolean NOT NULL DEFAULT false,
    archive_sha256 text NOT NULL,
    source_label text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS denue_editions_date_idx ON denue_editions(edition_date);

CREATE TABLE IF NOT EXISTS denue_grid_geometries (
    municipality_code text NOT NULL,
    grid_id text NOT NULL,
    geom geometry(MultiPolygon, 4326) NOT NULL,
    centroid geometry(Point, 4326) GENERATED ALWAYS AS (ST_PointOnSurface(geom)) STORED,
    area_m2 double precision GENERATED ALWAYS AS (ST_Area(geom::geography)) STORED,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (municipality_code, grid_id)
);
CREATE INDEX IF NOT EXISTS denue_grid_geometries_geom_gix ON denue_grid_geometries USING gist(geom);
CREATE INDEX IF NOT EXISTS denue_grid_geometries_centroid_gix ON denue_grid_geometries USING gist(centroid);
CREATE INDEX IF NOT EXISTS denue_grid_geometries_grid_idx ON denue_grid_geometries(grid_id);

CREATE TABLE IF NOT EXISTS denue_observations (
    id bigserial PRIMARY KEY,
    source_edition text NOT NULL REFERENCES denue_editions(source_edition) ON DELETE CASCADE,
    municipality_code text NOT NULL,
    ageb text NOT NULL,
    grid_id text NOT NULL,
    sector text NOT NULL,
    size_band smallint,
    scian6 text NOT NULL,
    postal_code text NOT NULL,
    contact_flags smallint NOT NULL DEFAULT 0 CHECK (contact_flags BETWEEN 0 AND 7),
    establishments integer NOT NULL CHECK (establishments > 0),
    has_phone boolean GENERATED ALWAYS AS ((contact_flags & 1) = 1) STORED,
    has_email boolean GENERATED ALWAYS AS ((contact_flags & 2) = 2) STORED,
    has_web boolean GENERATED ALWAYS AS ((contact_flags & 4) = 4) STORED,
    missing_ageb boolean GENERATED ALWAYS AS (ageb = 'SIN_AGEB') STORED,
    missing_grid boolean GENERATED ALWAYS AS (grid_id = 'SIN_GRID') STORED,
    missing_postal_code boolean GENERATED ALWAYS AS (postal_code = 'SIN_CP') STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (
        source_edition,
        municipality_code,
        ageb,
        grid_id,
        sector,
        size_band,
        scian6,
        postal_code,
        contact_flags
    )
);

CREATE INDEX IF NOT EXISTS denue_obs_edition_municipality_idx
    ON denue_observations(source_edition, municipality_code);
CREATE INDEX IF NOT EXISTS denue_obs_edition_grid_idx
    ON denue_observations(source_edition, municipality_code, grid_id);
CREATE INDEX IF NOT EXISTS denue_obs_edition_ageb_idx
    ON denue_observations(source_edition, municipality_code, ageb);
CREATE INDEX IF NOT EXISTS denue_obs_edition_sector_idx
    ON denue_observations(source_edition, sector);
CREATE INDEX IF NOT EXISTS denue_obs_edition_scian6_idx
    ON denue_observations(source_edition, scian6);
CREATE INDEX IF NOT EXISTS denue_obs_municipality_scian6_idx
    ON denue_observations(municipality_code, scian6, source_edition);

CREATE OR REPLACE VIEW denue_municipality_totals AS
SELECT
    o.source_edition,
    e.edition_date,
    e.is_rebenchmark,
    o.municipality_code,
    SUM(o.establishments)::bigint AS establishments,
    COUNT(DISTINCT NULLIF(o.ageb, 'SIN_AGEB')) AS active_agebs,
    COUNT(DISTINCT NULLIF(o.grid_id, 'SIN_GRID')) AS active_grids
FROM denue_observations o
JOIN denue_editions e USING (source_edition)
GROUP BY o.source_edition, e.edition_date, e.is_rebenchmark, o.municipality_code;

CREATE OR REPLACE VIEW denue_state_totals AS
SELECT
    o.source_edition,
    e.edition_date,
    e.is_rebenchmark,
    SUM(o.establishments)::bigint AS establishments
FROM denue_observations o
JOIN denue_editions e USING (source_edition)
GROUP BY o.source_edition, e.edition_date, e.is_rebenchmark;

COMMENT ON TABLE denue_observations IS
'Audited aggregated DENUE-derived territorial panel. Rows are grouped combinations with establishments as a count weight; they are not establishment-level microdata.';
