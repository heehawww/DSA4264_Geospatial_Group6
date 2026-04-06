# API

This folder contains the finalized FastAPI service for exposing the project's resale data, hedonic model outputs, school-specific RDD outputs, town premium outputs, diagnostics, and benchmark results.

The API is organized around the final analytical surfaces:

- historical resale records and summaries
- final hedonic model quality and explainability
- school-specific RDD results
- good-vs-non-good school comparison
- town-level premium estimates
- diagnostics
- model benchmark comparisons
- hypothetical price prediction

## Structure

- [main.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/main.py): FastAPI app composition
- [data.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/data.py): centralized artifact loading and prediction feature engineering
- [dependencies.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/dependencies.py): shared dependency accessors
- [schemas.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/schemas.py): Pydantic request and response models
- [routers/system.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/system.py): root, health, metadata
- [routers/resales.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/resales.py): historical resale rows and summaries
- [routers/model.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/model.py): final hedonic model metrics, feature importance, coefficients
- [routers/rdd.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/rdd.py): school-specific RDD results, coefficients, skipped schools, t-tests
- [routers/town_premiums.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/town_premiums.py): town-level premium outputs
- [routers/diagnostics.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/diagnostics.py): coefficient sign trace
- [routers/benchmarks.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/benchmarks.py): model benchmark results
- [routers/predict.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/predict.py): prediction schema and inference

## Data Loading

The API loads all required artifacts from the repo-level `data/` directory.

Current datasets used by the finalized API:

- `data/resale_flat_prices.csv`
- `data/resale_flats_with_school_buffer_counts_with_walkability.csv`
- `data/metrics.json`
- `data/feature_importance_top.csv`
- `data/ols_coefficients.csv`
- `data/ridge_pipeline.pkl`
- `data/school_specific_rdd_results.csv`
- `data/school_specific_rdd_coefficients.csv`
- `data/school_specific_rdd_skipped.csv`
- `data/school_group_ttests.csv`
- `data/rdd_summary.json`
- `data/town_premium_results.csv`
- `data/town_premium_skipped.csv`
- `data/good_school_sign_trace.csv`
- `data/benchmark_results.csv`
- `data/benchmark_results.json`
- `data/benchmark_metadata.json`

The raw resale API uses `data/resale_flat_prices.csv` as the current raw resale source.

The prediction API still uses the processed feature table `data/resale_flats_with_school_buffer_counts_with_walkability.csv` for default values and feature engineering because the raw resale file does not contain the amenity and school-walkability features needed by the saved ridge pipeline.

## Endpoint Inventory

### `GET /`

Service index listing all exposed endpoints.

### `GET /health`

Simple readiness check.

### `GET /metadata`

Provides the high-level API state:

- loaded data directory
- raw resale dataset availability
- row counts across all major analytical outputs
- loaded model metrics
- RDD summary metadata
- benchmark metadata

Use this first if the agent or frontend needs to inspect what is currently loaded.

## Resales

These endpoints are for observed historical resale data from `data/resale_flat_prices.csv`.

### `GET /resales/schema`

Returns:

- available columns in the current resale dataset
- supported filters
- supported `group_by` values

Use this for discovery, especially for LLM tool calling.

### `GET /resales/raw`

Returns row-level JSON records from the resale dataset.

Useful for:

- listing observed transactions
- retrieving example records in a town or month
- showing raw record-level resale rows

Supported filters include:

- `town`
- `flat_type`
- `flat_model`
- `street_name`
- `block`
- `storey_range`
- `month`
- `month_from`
- `month_to`
- `min_floor_area_sqm`
- `max_floor_area_sqm`
- `min_lease_commence_date`
- `max_lease_commence_date`
- `min_resale_price`
- `max_resale_price`

### `GET /resales/summary`

Returns aggregated summary statistics over the resale dataset.

Provides:

- count
- mean resale price
- median resale price
- min resale price
- max resale price

Also supports grouped summaries with:

- `group_by=town`
- `group_by=flat_type`
- `group_by=flat_model`
- `group_by=month`
- `group_by=storey_range`
- `group_by=street_name`

Use this for questions like:

- "What is the median resale price in Tampines?"
- "Compare resale prices by town."

## Model

These endpoints expose the finalized hedonic model outputs.

### `GET /model/metrics`

Source:

- `data/metrics.json`

Use for:

- showing prediction quality
- reporting held-out model performance
- justifying the final hedonic model choice

### `GET /model/feature-importance`

Source:

- `data/feature_importance_top.csv`

Use for:

- showing which features matter most to the predictive model
- explaining why the model behaves the way it does

### `GET /model/coefficients`

Source:

- `data/ols_coefficients.csv`

Use for:

- querying interpretable OLS terms
- searching for `good_school_within_1km`
- looking up individual model coefficients

### `GET /model/coefficients/{term_name}`

Convenience endpoint for retrieving one exact OLS coefficient row.

## Predict

### `GET /predict/schema`

Returns:

- raw request fields accepted by `POST /predict`
- engineered model fields used internally
- dataset-backed defaults
- example allowed categories

This endpoint helps the agent explain what inputs users can provide.

### `POST /predict`

Uses the saved ridge regression pipeline in `data/ridge_pipeline.pkl`.

It:

1. accepts a user-facing flat specification
2. fills in missing fields using dataset-backed defaults
3. engineers the exact features expected by the model
4. returns a predicted resale price

The response includes:

- `predicted_price`
- `used_defaults`
- `provided_raw_fields`
- `defaulted_raw_fields`
- `warning`
- `engineered_features_used`

This is for hypothetical model inference, not historical lookup.

## RDD

These endpoints expose the finalized school-specific RDD outputs.

### `GET /rdd/summary`

Source:

- `data/rdd_summary.json`

Use for:

- overall RDD metadata
- number of rows and schools covered
- bandwidths and run summary

### `GET /rdd/schools`

Derived from:

- `data/school_specific_rdd_results.csv`
- `data/school_specific_rdd_skipped.csv`

Provides school-level coverage information such as:

- which schools have successful RDD result rows
- which schools have skipped rows
- counts of results vs skipped entries

### `GET /rdd/results`

Source:

- `data/school_specific_rdd_results.csv`

This is one of the main analytical endpoints.

Use for:

- school-specific sample sizes
- local premium percent
- local premium in SGD
- p-values
- confidence intervals

Supported filters:

- `school_name`
- `school_group`
- `specification`
- `bandwidth_m`

### `GET /rdd/results/{school_name}`

Convenience endpoint returning RDD rows for one school.

### `GET /rdd/coefficients`

Source:

- `data/school_specific_rdd_coefficients.csv`

Use for:

- inspecting the full coefficient tables behind school-specific RDD fits
- filtering by school, specification, bandwidth, or term

### `GET /rdd/group-ttests`

Source:

- `data/school_group_ttests.csv`

This is the endpoint for answering:

- whether good schools have significantly different local premiums than non-good schools

### `GET /rdd/skipped`

Source:

- `data/school_specific_rdd_skipped.csv`

This is the coverage and feasibility endpoint.

Use for:

- which schools were excluded
- why some schools do not appear in the main RDD results
- filtering skipped schools by reason, school name, school group, or bandwidth

## Town Premiums

These endpoints expose the finalized town-level premium outputs.

### `GET /town-premiums/summary`

Provides overall summary statistics across town-specific premium models.

### `GET /town-premiums`

Source:

- `data/town_premium_results.csv`

Use for:

- listing town-level premium estimates
- comparing towns
- filtering by p-value

### `GET /town-premiums/{town_name}`

Convenience endpoint for one town's premium result.

### `GET /town-premiums/skipped`

Source:

- `data/town_premium_skipped.csv`

Use for:

- seeing which towns were excluded
- understanding why some towns do not appear in the town premium results

## Diagnostics

### `GET /diagnostics/sign-trace`

Source:

- `data/good_school_sign_trace.csv`

Use for:

- tracing how the `good_school_within_1km` coefficient changes sign and magnitude as controls are added
- internal model interpretation and diagnostic analysis

## Benchmarks

These endpoints expose the benchmark comparison outputs you generated from `benchmark_hedonic_variants.py`.

### `GET /benchmarks/summary`

Provides:

- number of benchmarked variants
- best variant by test `R^2`
- best variant by test RMSE
- benchmark metadata

### `GET /benchmarks/results`

Source:

- `data/benchmark_results.csv`

Use for:

- comparing all model variants
- showing tradeoffs across test metrics
- justifying why the final model was chosen

### `GET /benchmarks/best`

Convenience endpoint that returns the best variant by:

- test `R^2`
- test RMSE
- test MAE

### `GET /benchmarks/metadata`

Source:

- `data/benchmark_metadata.json`

Use for:

- benchmark configuration
- train/test row counts
- feature-pruning metadata

## Recommended Endpoint Selection

Use:

- `/resales/raw` and `/resales/summary` for observed historical data
- `/model/metrics` and `/model/feature-importance` for prediction quality and model justification
- `/rdd/results` for school-specific RDD main results
- `/rdd/group-ttests` for good-vs-non-good comparison
- `/rdd/skipped` for coverage and feasibility explanation
- `/town-premiums` for town-level premium estimates
- `/diagnostics/sign-trace` for coefficient-sign diagnostics
- `/benchmarks/*` for benchmark comparison and final model-choice justification
- `/predict` for hypothetical flat price prediction

## Environment Setup

This repo includes both:

- `pyproject.toml`
- `uv.lock`

### Using `uv`

This is the recommended and most reproducible path:

```bash
uv sync
uv run uvicorn api.main:app --reload
```

### Using `pip`

If you prefer `pip`, install from `pyproject.toml`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Important:

- `pip` does not use `uv.lock` directly
- `pip install -e .` reads dependencies from `pyproject.toml`
- `uv` is the better choice if you want to stay aligned with the locked environment

## Running The App

From the repository root:

```bash
uv run uvicorn api.main:app --reload
```
