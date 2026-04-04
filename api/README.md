# API

This folder contains the FastAPI app for exposing the project datasets and model artifacts to a downstream chat or agent layer.

The API is intentionally split into:

- historical data endpoints
- model interpretation endpoints
- aggregated RDD endpoints
- scored premium endpoints
- hypothetical prediction endpoints

That distinction matters because these outputs answer different kinds of user questions.

## Structure

- [main.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/main.py): app factory/composition only
- [data.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/data.py): artifact loading and prediction feature engineering
- [dependencies.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/dependencies.py): shared dependency accessors
- [schemas.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/schemas.py): Pydantic request and response models
- [routers/system.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/system.py): root, health, metadata
- [routers/ols.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/ols.py): OLS coefficient endpoints
- [routers/model.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/model.py): saved model metrics
- [routers/rdd.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/rdd.py): pooled RDD outputs
- [routers/premiums.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/premiums.py): model-scored premium rows
- [routers/resales.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/resales.py): historical rows and aggregates
- [routers/predict.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/predict.py): prediction schema and ridge inference

This structure keeps:

- routing concerns in router modules
- data loading and feature engineering in one place
- request and response contracts in Pydantic schemas
- `main.py` focused on app composition only

## Data Loading

The API loads its artifacts from the repo-level `data/` folder.

Current required files:

- `data/resale_flats_with_school_buffer_counts_with_walkability.csv`
- `data/ols_coefficients.csv`
- `data/metrics.json`
- `data/ridge_pipeline.pkl`
- `data/rdd_results.csv`
- `data/rdd_summary.json`
- `data/flat_school_premiums_treated_only.csv`
- `data/scoring_summary.json`

Optional final file:

- `data/resale_hdbs_raw.csv`
- `data/resale_flat_prices.csv`

If both `data/resale_hdbs_raw.csv` and `data/resale_flat_prices.csv` are missing, `/resales/raw` and `/resales/summary` fall back to the processed feature table and explicitly say so in the response.

## Endpoint Inventory

### `GET /`

Service index of the available endpoints.

### `GET /health`

Simple readiness check.

### `GET /metadata`

Returns high-level dataset and model metadata:

- loaded paths
- row counts
- model metrics
- premium summary
- RDD summary
- raw dataset availability

This is the best first endpoint for an agent that wants to inspect current system state.

### `GET /ols/coefficients`

Returns rows from the saved OLS coefficient table.

Useful for:

- coefficient lookup
- term search
- significant-only filtering

### `GET /ols/coefficients/{term_name}`

Returns one exact coefficient row by term name.

### `GET /model/metrics`

Returns the saved hedonic model metrics JSON.

### `GET /rdd/summary`

Returns high-level metadata for the aggregated pooled RDD run.

### `GET /rdd/results`

Returns aggregated pooled RDD result rows.

Supports:

- `specification`
- `bandwidth_m`
- `limit`

Important:

- these are currently aggregated pooled results
- these are not school-specific RDD estimates

### `GET /premiums/summary`

Returns overall summary statistics for the scored premium dataset.

### `GET /premiums`

Returns transaction-level scored premium rows from the treated-only premium dataset.

Supports:

- multiple `town` filters
- multiple `flat_type` filters
- min/max premium filters

Important:

- these premiums are model-derived
- they are not observed premiums
- they should not be framed as flat-level causal effects

### `GET /resales/raw`

Returns row-level JSON records from:

- the true raw resale file, if present
- the `data/resale_flat_prices.csv` raw resale file, if present
- otherwise the processed feature-table fallback

Supports:

- multiple `town` filters
- multiple `flat_type` filters
- multiple `flat_model` filters
- multiple `street_name` filters
- multiple `block` filters
- multiple `storey_range` filters
- multiple `month` filters
- `month_from`
- `month_to`
- `min_floor_area_sqm`
- `max_floor_area_sqm`
- `min_lease_commence_date`
- `max_lease_commence_date`
- `min_resale_price`
- `max_resale_price`
- `min_school_count_1km`
- `max_school_count_1km`
- `min_good_school_count_1km`
- `max_good_school_count_1km`
- `min_school_count_2km`
- `max_school_count_2km`
- `min_good_school_count_2km`
- `max_good_school_count_2km`

The response contains:

- `is_true_raw_dataset`
- `dataset_kind`
- `note`

These fields are important for the chat layer because they prevent accidental overclaiming when the raw CSV is not yet loaded.

### `GET /resales/schema`

Returns the curated resale query contract:

- currently available columns in the backing dataset
- supported filters
- supported `group_by` fields
- notes on whether the API is using the true raw file or the processed fallback

This endpoint is especially useful for LLM or frontend integration because it lets the caller discover the supported query surface instead of hardcoding assumptions.

### `GET /resales/summary`

Returns aggregated resale statistics over the dataset currently backing `/resales/raw`.

Supports:

- multiple `town` filters
- multiple `flat_type` filters
- multiple `flat_model` filters
- multiple `street_name` filters
- multiple `block` filters
- multiple `storey_range` filters
- `month_from`
- `month_to`
- `min_floor_area_sqm`
- `max_floor_area_sqm`
- `min_lease_commence_date`
- `max_lease_commence_date`
- `min_resale_price`
- `max_resale_price`
- `min_school_count_1km`
- `max_school_count_1km`
- `min_good_school_count_1km`
- `max_good_school_count_1km`
- `min_school_count_2km`
- `max_school_count_2km`
- `min_good_school_count_2km`
- `max_good_school_count_2km`
- `group_by=town|flat_type|flat_model|month|storey_range`

Behavior:

- if `group_by` is omitted, the summary is combined across all matched rows
- if `group_by` is supplied, separate grouped rows are returned

### `GET /predict/schema`

Returns the prediction contract for `POST /predict`:

- accepted raw request fields
- engineered model fields used internally
- dataset-backed defaults
- sample allowed categories

This is intended for agent or frontend use when explaining what can be provided by a user.

### `POST /predict`

Returns a hypothetical ridge-model price prediction.

The endpoint:

1. accepts raw user-facing flat inputs
2. fills missing inputs using dataset-backed defaults
3. engineers the model features expected by the saved ridge pipeline
4. predicts the log price and converts it back to SGD

The response includes:

- `predicted_price`
- `used_defaults`
- `provided_raw_fields`
- `defaulted_raw_fields`
- `warning`
- `engineered_features_used`

This is useful for chat because the LLM can be upfront when the prediction relied heavily on defaults.

## Derivation Context

### OLS coefficients

Source:

- `data/ols_coefficients.csv`

Derived from the hedonic OLS regression fitted in `hedonic_model/train_hedonic_model.py`.

These are interpretation outputs, not historical rows.

### Model metrics

Source:

- `data/metrics.json`

Derived from the ridge predictive model and accompanying saved training metrics.

### RDD outputs

Sources:

- `data/rdd_results.csv`
- `data/rdd_summary.json`

Derived from `hedonic_model/run_school_boundary_rdd.py`.

The current API only exposes aggregated pooled RDD results, not school-specific results.

### Premium outputs

Sources:

- `data/flat_school_premiums_treated_only.csv`
- `data/scoring_summary.json`

Derived from `hedonic_model/score_school_premium.py`.

These represent model-scored premiums for treated flats only.

### Resale summaries and raw rows

Primary intended source:

- `data/resale_hdbs_raw.csv`

Current fallback source if the raw file is missing:

- `data/resale_flats_with_school_buffer_counts_with_walkability.csv`

The fallback table is processed and feature-enriched. It should not be casually described as a raw dataset.

## How The Agent Layer Should Think About This API

The API does not infer intent. The chat layer should choose the correct endpoint.

Use:

- `/resales/schema` for discovery of resale filters and groupings
- `/resales/raw` for historical row-level retrieval
- `/resales/summary` for historical aggregates
- `/ols/*` for coefficient interpretation
- `/rdd/*` for discontinuity outputs
- `/premiums*` for model-scored premiums
- `/predict` for hypothetical flat pricing

Examples:

- "What was the median resale price in Tampines?" -> `/resales/summary`
- "Show me some resale records in Bedok." -> `/resales/raw`
- "What is the coefficient on good_school_within_1km?" -> `/ols/coefficients/good_school_within_1km`
- "What are the RDD results at 300m?" -> `/rdd/results`
- "Show me treated flats in Ang Mo Kio with premium estimates." -> `/premiums`
- "How much would this flat cost?" -> `/predict`

## Unknowns To Fill In Later

These are not fully specified from the current workspace alone and should not be guessed by future developers:

- the exact final schema and provenance of `data/resale_hdbs_raw.csv`
- whether `data/resale_flat_prices.csv` is now the team's intended canonical raw resale file name, or just one accepted variant
- the authoritative business rule for what qualifies as a "good" primary school
- whether map-ready or GeoJSON endpoints are needed in the final product
- whether the team wants a default RDD specification and bandwidth for vague user questions

## Running The App

## Environment Setup

This repo includes both:

- `pyproject.toml`
- `uv.lock`

So you can install dependencies with either `uv` or `pip`, depending on your workflow.

### Option 1: Using `uv` with the lockfile

This is the most reproducible option if you want to respect the pinned environment in `uv.lock`.

From the repository root:

```bash
uv sync
```

Then run the API with:

```bash
uv run uvicorn api.main:app --reload
```

### Option 2: Using `uv` from `pyproject.toml`

If you want `uv` to create/update the environment from the project metadata:

```bash
uv sync
```

This uses `pyproject.toml`, and if `uv.lock` is present it will also use the lockfile state.

### Option 3: Using `pip`

If you prefer `pip`, create and activate a virtual environment first, then install from `pyproject.toml`.

Editable install:

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

- `pip` does not install directly from `uv.lock`
- `pip install -e .` reads the dependency list from `pyproject.toml`
- `requirements.txt` in this repo is not the source of truth for the API environment
- `uv` is the better choice if you want to stay aligned with the locked dependency set

## Running The App

From the repository root:

```bash
uvicorn api.main:app --reload
```

Or with the project environment if available:

```bash
uv run uvicorn api.main:app --reload
```
