# Feature Engineering

This module consolidates the geospatial school-boundary feature steps and the
walkability feature steps into one place.

## Structure

- `main.py`: orchestration entrypoint
- `steps/primary_boundaries/`: school-boundary and resale-point feature steps
- `steps/walkability/`: amenity walkability feature scripts

## Data Layout

The shared feature-engineering data layout is:

- `data/feature_engineering/inputs/`
- `data/feature_engineering/intermediate/`
- `data/feature_engineering/outputs/`

The canonical engineered dataset used downstream is:

- `data/feature_engineering/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv`

Other commonly used canonical outputs include:

- `data/feature_engineering/outputs/resale_flats_with_school_buffer_counts.csv`
- `data/feature_engineering/outputs/resale_address_points_matched_with_school_counts.geojson`
- `data/feature_engineering/outputs/primary_school_boundaries_buffer_1km.geojson`
- `data/feature_engineering/outputs/primary_school_boundaries_buffer_2km.geojson`
- `data/feature_engineering/outputs/hdb_existing_buildings_layer.geojson`

## Inputs

The step scripts still keep their own default assumptions, but the intended
shared input home is:

- `data/feature_engineering/inputs/`

Typical source files include raw resale data, school location summaries, URA
land-use polygons, HDB building geometries, MRT exit data, and amenity
GeoJSON inputs.

## Step Groups

The pipeline is currently split into two step groups:

- `steps/primary_boundaries/`
  Covers school-to-URA joins, school classification, school boundary layers,
  MRT/shopping-centre layers, HDB building layers, and resale-point school
  feature generation.
- `steps/walkability/`
  Covers walkability features for bus stops, hawker centres, parks, and
  supermarkets.

The current setup keeps the step scripts mostly intact and uses `main.py` to
coordinate them and sync produced artifacts into the canonical data directory.

## Running

Sync the current step outputs into the canonical data directory:

```powershell
python -m feature_engineering.main sync-outputs
```

Run one step script by name:

```powershell
python -m feature_engineering.main run-step build_primary_school_boundaries
python -m feature_engineering.main run-step classify_good_schools
```

Run the currently defined boundary pipeline and then sync outputs:

```powershell
python -m feature_engineering.main run-pipeline
```

The walkability-enriched final CSV is currently treated as an existing produced
artifact and synced into `data/feature_engineering/outputs/`. A future cleanup
can add a fully reproducible merge step into this module.
