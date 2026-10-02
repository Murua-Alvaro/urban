# Spatial EDA

Spatial EDA builds complete municipality-by-edition panels for AGEBs and 1 km grids, filling inactive periods with zero so appearance/disappearance and net-stock-change proxies are explicit. These are territorial stock transitions, not establishment-level births/deaths because the compact dataset does not retain individual DENUE IDs.

Outputs include territorial stock, first/last active date, sector diversity, grid concentration (HHI, entropy, Gini, top-node shares, rank-size slope), grid geometry/area, establishments per grid-km2 and optional global Moran's I using Queen contiguity. Rebenchmark transitions remain flagged and must not be interpreted as pure local economic growth.
