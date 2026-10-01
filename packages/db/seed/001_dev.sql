INSERT INTO variable_catalog(variable, label, domain, unit, description, source_priority) VALUES
('population','Population','demography','persons','Resident population for the geography','["INEGI Census","Intercensal"]'),
('households','Households','demography','households','Occupied private households','["INEGI Census"]'),
('establishments','Establishments','economy','count','Economic establishments located in the geography','["DENUE"]'),
('employment_proxy','Employment proxy','economy','persons','Employment or employment-band midpoint proxy','["DENUE","IMSS"]'),
('listing_price_m2','Listing price per m2','real_estate','MXN/m2','Observed asking price normalized by built or land area','["uploaded listings"]'),
('built_density','Built density','urban_form','ratio','Built area divided by land area','["INV","cadastre","remote sensing"]'),
('amenity_access','Amenity accessibility','accessibility','index','Distance-decay accessibility to selected amenities','["DENUE","OSM"]'),
('economic_diversity','Economic diversity','economy','index','Entropy-based diversity across SCIAN activities','["DENUE"]')
ON CONFLICT (variable) DO NOTHING;

INSERT INTO model_specifications(key,label,model_family,dependent_variable,regressors,fixed_effects,robust_covariance,spatial_weights,notes) VALUES
('price_hedonic_base','Hedonic listing-price baseline','OLS','log_listing_price_m2','["log_area_built_m2","bedrooms","bathrooms","amenity_access","economic_diversity"]','["period"]','HC3',NULL,'Baseline cross-sectional specification with robust covariance.'),
('price_panel_fe','Urban price panel fixed effects','PanelFE','log_listing_price_m2','["amenity_access","establishments","built_density","population"]','["geography","period"]','clustered',NULL,'Within estimator with geography and period effects.'),
('price_spatial_lag','Spatial lag price model','SAR','log_listing_price_m2','["amenity_access","economic_diversity","built_density"]','[]','spatial','{"type":"knn","k":8,"row_standardized":true}','Spatial dependence specification; compare against OLS residual Moran I.')
ON CONFLICT (key) DO NOTHING;

-- Synthetic development seed: deterministic and explicitly non-official.
INSERT INTO datasets(id,name,source_type,original_filename,sha256,status,metadata)
VALUES ('00000000-0000-0000-0000-000000000001','Urban synthetic development seed','seed','seed.sql',repeat('0',64),'normalized','{"synthetic":true,"purpose":"development and automated tests"}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO geographies(geokey,geography_type,name,parent_geokey,centroid,area_m2,metadata) VALUES
('DEV-MZT-001','grid','Synthetic urban cell 001','25012',ST_SetSRID(ST_MakePoint(-106.42,23.24),4326),250000,'{"synthetic":true}'),
('DEV-MZT-002','grid','Synthetic urban cell 002','25012',ST_SetSRID(ST_MakePoint(-106.41,23.24),4326),250000,'{"synthetic":true}')
ON CONFLICT (geokey) DO NOTHING;

INSERT INTO urban_observations(dataset_id,geography_id,period,variable,value,unit,source,quality_flag,metadata)
SELECT '00000000-0000-0000-0000-000000000001', g.id, DATE '2025-01-01', v.variable, v.value, v.unit, 'synthetic_seed', 'synthetic', '{"synthetic":true}'::jsonb
FROM geographies g
JOIN (VALUES
  ('DEV-MZT-001','population',1850.0,'persons'),
  ('DEV-MZT-001','establishments',74.0,'count'),
  ('DEV-MZT-001','economic_diversity',0.71,'index'),
  ('DEV-MZT-002','population',2310.0,'persons'),
  ('DEV-MZT-002','establishments',103.0,'count'),
  ('DEV-MZT-002','economic_diversity',0.79,'index')
) AS v(geokey,variable,value,unit) ON v.geokey = g.geokey
ON CONFLICT DO NOTHING;
