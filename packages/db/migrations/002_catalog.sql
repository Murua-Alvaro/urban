CREATE TABLE IF NOT EXISTS variable_catalog (
    variable text PRIMARY KEY,
    label text NOT NULL,
    domain text NOT NULL,
    unit text,
    expected_type text NOT NULL DEFAULT 'numeric',
    description text,
    source_priority jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_specifications (
    key text PRIMARY KEY,
    label text NOT NULL,
    model_family text NOT NULL,
    dependent_variable text NOT NULL,
    regressors jsonb NOT NULL,
    fixed_effects jsonb NOT NULL DEFAULT '[]'::jsonb,
    robust_covariance text,
    spatial_weights jsonb,
    notes text,
    enabled boolean NOT NULL DEFAULT true
);

CREATE OR REPLACE VIEW latest_urban_observations AS
SELECT DISTINCT ON (geography_id, variable, source)
    geography_id, variable, source, period, value, unit, quality_flag, metadata
FROM urban_observations
ORDER BY geography_id, variable, source, period DESC;
