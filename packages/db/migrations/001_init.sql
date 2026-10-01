CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS datasets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    source_type text NOT NULL DEFAULT 'zip_upload',
    original_filename text,
    sha256 text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','validated','normalized','failed')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dataset_assets (
    id bigserial PRIMARY KEY,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    path text NOT NULL,
    extension text NOT NULL,
    size_bytes bigint NOT NULL,
    row_count bigint,
    columns jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(dataset_id, path)
);

CREATE TABLE IF NOT EXISTS geographies (
    id bigserial PRIMARY KEY,
    geokey text NOT NULL UNIQUE,
    geography_type text NOT NULL CHECK (geography_type IN ('state','municipality','locality','ageb','block','grid','neighborhood','property')),
    name text,
    parent_geokey text,
    geom geometry(MultiPolygon, 4326),
    centroid geometry(Point, 4326),
    area_m2 double precision,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS geographies_geom_gix ON geographies USING gist(geom);
CREATE INDEX IF NOT EXISTS geographies_centroid_gix ON geographies USING gist(centroid);
CREATE INDEX IF NOT EXISTS geographies_type_idx ON geographies(geography_type);

CREATE TABLE IF NOT EXISTS properties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id uuid REFERENCES datasets(id) ON DELETE SET NULL,
    external_id text,
    geography_id bigint REFERENCES geographies(id) ON DELETE SET NULL,
    address text,
    neighborhood text,
    property_type text,
    listing_type text,
    price numeric(18,2),
    area_land_m2 double precision,
    area_built_m2 double precision,
    bedrooms smallint,
    bathrooms numeric(4,1),
    latitude double precision,
    longitude double precision,
    geom geometry(Point, 4326),
    observed_at date,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(dataset_id, external_id)
);
CREATE INDEX IF NOT EXISTS properties_geom_gix ON properties USING gist(geom);
CREATE INDEX IF NOT EXISTS properties_price_idx ON properties(price);
CREATE INDEX IF NOT EXISTS properties_observed_idx ON properties(observed_at);

CREATE TABLE IF NOT EXISTS urban_observations (
    id bigserial PRIMARY KEY,
    dataset_id uuid REFERENCES datasets(id) ON DELETE SET NULL,
    geography_id bigint NOT NULL REFERENCES geographies(id) ON DELETE CASCADE,
    period date NOT NULL,
    variable text NOT NULL,
    value double precision,
    unit text,
    source text,
    quality_flag text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(geography_id, period, variable, source)
);
CREATE INDEX IF NOT EXISTS urban_observations_lookup_idx ON urban_observations(variable, period, geography_id);

CREATE TABLE IF NOT EXISTS model_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id uuid REFERENCES datasets(id) ON DELETE SET NULL,
    model_family text NOT NULL,
    specification_name text NOT NULL,
    dependent_variable text NOT NULL,
    formula text,
    spatial_weight_spec jsonb,
    sample_definition jsonb NOT NULL DEFAULT '{}'::jsonb,
    diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    code_version text,
    random_seed integer,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS model_coefficients (
    id bigserial PRIMARY KEY,
    model_run_id uuid NOT NULL REFERENCES model_runs(id) ON DELETE CASCADE,
    term text NOT NULL,
    estimate double precision,
    std_error double precision,
    statistic double precision,
    p_value double precision,
    conf_low double precision,
    conf_high double precision,
    robust_method text,
    UNIQUE(model_run_id, term)
);

CREATE TABLE IF NOT EXISTS ingestion_events (
    id bigserial PRIMARY KEY,
    dataset_id uuid REFERENCES datasets(id) ON DELETE CASCADE,
    stage text NOT NULL,
    status text NOT NULL,
    message text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
