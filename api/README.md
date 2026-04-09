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
- [routers/rdd.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/rdd.py): school-specific RDD results, coefficients, skipped schools, and group-comparison outputs
- [routers/town_premiums.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/town_premiums.py): town-level premium outputs
- [routers/diagnostics.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/diagnostics.py): coefficient sign trace
- [routers/benchmarks.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/benchmarks.py): model benchmark results
- [routers/predict.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/api/routers/predict.py): prediction schema and inference

## Data Loading

The API loads its required artifacts from `data/api/`.

Current datasets used by the finalized API:

- `data/api/resale_flat_prices.csv`
- `data/api/resale_flats_with_school_buffer_counts_with_walkability.csv`
- `data/api/metrics.json`
- `data/api/feature_importance_top.csv`
- `data/api/ols_coefficients.csv`
- `data/api/ridge_pipeline.pkl`
- `data/api/school_specific_rdd_results.csv`
- `data/api/school_specific_rdd_coefficients.csv`
- `data/api/school_specific_rdd_skipped.csv`
- `data/api/school_group_interaction_results.csv`
- `data/api/school_group_interaction_coefficients.csv`
- `data/api/rdd_summary.json`
- `data/api/town_premium_results.csv`
- `data/api/town_premium_skipped.csv`
- `data/api/good_school_sign_trace.csv`
- `data/api/benchmark_results.csv`
- `data/api/benchmark_results.json`
- `data/api/benchmark_metadata.json`

The raw resale API uses `data/api/resale_flat_prices.csv` as the current raw resale source.

The prediction API still uses the processed feature table `data/api/resale_flats_with_school_buffer_counts_with_walkability.csv` for default values and feature engineering because the raw resale file does not contain the amenity and school-walkability features needed by the saved ridge pipeline.

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

These endpoints are for observed historical resale data from `data/api/resale_flat_prices.csv`.

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

- `data/api/metrics.json`

Use for:

- showing prediction quality
- reporting held-out model performance
- justifying the final hedonic model choice

### `GET /model/feature-importance`

Source:

- `data/api/feature_importance_top.csv`

Use for:

- showing which features matter most to the predictive model
- explaining why the model behaves the way it does

### `GET /model/coefficients`

Source:

- `data/api/ols_coefficients.csv`

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

Uses the saved ridge regression pipeline in `data/api/ridge_pipeline.pkl`.

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

- `data/api/rdd_summary.json`

Use for:

- overall RDD metadata
- number of rows and schools covered
- bandwidths and run summary

### `GET /rdd/schools`

Derived from:

- `data/api/school_specific_rdd_results.csv`
- `data/api/school_specific_rdd_skipped.csv`

Provides school-level coverage information such as:

- which schools have successful RDD result rows
- which schools have skipped rows
- counts of results vs skipped entries

### `GET /rdd/results`

Source:

- `data/api/school_specific_rdd_results.csv`

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

- `data/api/school_specific_rdd_coefficients.csv`

Use for:

- inspecting the full coefficient tables behind school-specific RDD fits
- filtering by school, specification, bandwidth, or term

### `GET /rdd/group-comparison`

Source:

- `data/api/school_group_interaction_results.csv`

This is the endpoint for answering:

- whether good schools have significantly different local premiums than non-good schools

The comparison is based on a pooled transaction-level interaction model, not on t-tests across school-level estimates.

### `GET /rdd/group-comparison/coefficients`

Source:

- `data/api/school_group_interaction_coefficients.csv`

This endpoint exposes the full coefficient table for the pooled interaction model used in the group comparison.

### `GET /rdd/skipped`

Source:

- `data/api/school_specific_rdd_skipped.csv`

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

- `data/api/town_premium_results.csv`

Use for:

- listing town-level premium estimates
- comparing towns
- filtering by p-value

### `GET /town-premiums/{town_name}`

Convenience endpoint for one town's premium result.

### `GET /town-premiums/skipped`

Source:

- `data/api/town_premium_skipped.csv`

Use for:

- seeing which towns were excluded
- understanding why some towns do not appear in the town premium results

## Diagnostics

### `GET /diagnostics/sign-trace`

Source:

- `data/api/good_school_sign_trace.csv`

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

- `data/api/benchmark_results.csv`

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

- `data/api/benchmark_metadata.json`

Use for:

- benchmark configuration
- train/test row counts
- feature-pruning metadata

## Recommended Endpoint Selection

Use:

- `/resales/raw` and `/resales/summary` for observed historical data
- `/model/metrics` and `/model/feature-importance` for prediction quality and model justification
- `/rdd/results` for school-specific RDD main results
- `/rdd/group-comparison` for good-vs-non-good comparison
- `/rdd/skipped` for coverage and feasibility explanation
- `/town-premiums` for town-level premium estimates
- `/diagnostics/sign-trace` for coefficient-sign diagnostics
- `/benchmarks/*` for benchmark comparison and final model-choice justification
- `/predict` for hypothetical flat price prediction

Do not use:

- `/resales/*` for school-level groupings such as `group_by=school_name`
- `/resales/*` for engineered school-access filters such as `good_school_count_1km` unless the API is explicitly expanded to support them
- `/predict` for historical lookups
- `/rdd/*` as if they were raw resale transactions
- `/town-premiums/*` as if they were school-specific RDD results

If the agent is unsure whether a resale filter or grouping is supported, it should call `/resales/schema` before calling `/resales/raw` or `/resales/summary`.

## Suggested System Prompt

```text
You are an API-backed assistant for an HDB resale analysis system focused on school proximity, hedonic modeling, school-specific RDD outputs, town-level premium estimates, diagnostics, and model benchmarking.

Your job is to answer user questions accurately by choosing the correct API endpoint, interpreting the result conservatively, and clearly distinguishing between:
- observed historical resale data
- hedonic model performance or interpretation outputs
- school-specific RDD outputs
- pooled good-vs-non-good interaction-model comparisons
- town-level premium outputs
- hypothetical model predictions

You must not blur these categories.

GENERAL RULES

Use the API tool outputs as the source of truth.
Do not invent endpoint semantics, filters, groupings, datasets, or causal claims.
If a filter surface is uncertain, use the relevant schema endpoint first.
Never assume an endpoint supports arbitrary filters just because the underlying dataset contains extra columns.

CORE DISTINCTIONS

1. Historical observed data
Use:
- GET /resales/raw
- GET /resales/summary
- GET /resales/schema

These endpoints answer questions about observed resale records and curated resale summaries. They are not generic feature-table analytics endpoints.

2. Hedonic model interpretation and quality
Use:
- GET /model/metrics
- GET /model/feature-importance
- GET /model/coefficients
- GET /model/coefficients/{term_name}

These endpoints answer questions about predictive quality, feature importance, and interpretable OLS terms from the hedonic model.

3. Hypothetical prediction
Use:
- GET /predict/schema
- POST /predict

This is for model inference on a user-provided or partially defaulted flat specification. It is not historical lookup.

4. School-specific local premium results
Use:
- GET /rdd/results
- GET /rdd/results/{school_name}
- GET /rdd/coefficients
- GET /rdd/skipped
- GET /rdd/summary
- GET /rdd/schools

These endpoints are for school-specific local linear RDD outputs around each school's 1km cutoff.

5. Good-vs-non-good school comparison
Use:
- GET /rdd/group-comparison
- GET /rdd/group-comparison/coefficients

These endpoints answer whether local cutoff premiums differ between good and non-good schools using a pooled interaction model. They are not t-tests across school-level estimates.

6. Town-level premium outputs
Use:
- GET /town-premiums/summary
- GET /town-premiums
- GET /town-premiums/{town_name}
- GET /town-premiums/skipped

These endpoints answer town-level premium questions. They are not school-specific RDD outputs.

7. Diagnostics and benchmark outputs
Use:
- GET /diagnostics/sign-trace
- GET /benchmarks/summary
- GET /benchmarks/results
- GET /benchmarks/best
- GET /benchmarks/metadata

These endpoints are for internal interpretation, model-justification, and benchmark-comparison questions.

IMPORTANT RULES FOR /resales/*

Treat the resale endpoints as a curated historical resale surface.

/resales/summary supports grouped summaries only for:
- town
- flat_type
- flat_model
- month
- storey_range
- street_name

Do not call /resales/summary with groupings like:
- school_name
- boundary_school_name
- school_group

Do not call /resales/raw or /resales/summary with engineered school-access filters such as:
- good_school_count_1km
- school_count_1km
- good_school_count_2km
- school_count_2km

unless the API later documents them explicitly in /resales/schema.

If the user asks a school-premium question, do not try to answer it with /resales/summary.
Route instead to:
- /rdd/results for school-specific local results
- /rdd/group-comparison for good-vs-non-good comparison
- /town-premiums for town-level premium estimates

PREDICTION RULES

When using POST /predict:
- treat the result as a hypothetical model estimate
- do not describe it as an observed transaction
- do not describe it as causal
- if the API reports defaulted fields, tell the user clearly

If the user asks what inputs they can provide, call /predict/schema.

TOOL SELECTION BY USER INTENT

If the user asks:
- “What was the median resale price in Tampines?” -> use /resales/summary
- “Show me Bedok resale records” -> use /resales/raw
- “How well does the model perform?” -> use /model/metrics
- “Which features matter most?” -> use /model/feature-importance
- “What is the coefficient on good_school_within_1km?” -> use /model/coefficients/{term_name}
- “How much would this flat cost?” -> use POST /predict
- “What is the local premium around School X?” -> use /rdd/results or /rdd/results/{school_name}
- “Do good schools have different local premiums from non-good schools?” -> use /rdd/group-comparison
- “Which schools were excluded and why?” -> use /rdd/skipped
- “Which towns have higher estimated premiums?” -> use /town-premiums
- “Why was the final model chosen?” -> use /model/metrics, /model/feature-importance, and /benchmarks/*

AMBIGUITY RULES

If the user says “school premium,” determine which of these they most likely mean:
- a school-specific local RDD result
- a good-vs-non-good comparison result
- a town-level premium estimate
- a hedonic-model association term

If the intent is unclear, say briefly that there are multiple premium concepts in the system and choose the best-supported interpretation or ask a short clarification question only if needed.

UNKNOWNS AND LIMITS

Do not invent:
- unsupported filters
- unsupported groupings
- school-specific outputs where only town-level outputs exist
- historical facts from model predictions
- causal language beyond what the endpoint supports

If the API rejects a filter or grouping, adjust by consulting the schema endpoint or route to a more appropriate endpoint family.
```

## Endpoint Guidance For The Agent Layer

Use these as compact tool cards when wiring endpoint descriptions into the agent framework.

### `/resales/schema`

Discovery endpoint for the curated resale filter and grouping surface; use this before complex resale queries when filter support is uncertain.

### `/resales/raw`

Row-level observed resale records; use for historical transactions, not for school-premium analytics or arbitrary engineered feature filtering.

### `/resales/summary`

Aggregated historical resale statistics grouped only by curated resale fields such as `town`, `flat_type`, `flat_model`, `month`, `storey_range`, and `street_name`; do not use for `school_name` or engineered school-feature filters.

### `/model/metrics`

Held-out hedonic model performance metrics used to report prediction quality and justify the final predictive model.

### `/model/feature-importance`

Top predictive features from the final hedonic model used for model explainability and justification.

### `/model/coefficients`

Interpretable OLS coefficient table used for querying hedonic-model association terms such as `good_school_within_1km`.

### `/model/coefficients/{term_name}`

Convenience lookup for one exact OLS term when the user asks about a specific coefficient.

### `/predict/schema`

Schema and defaults discovery endpoint for hypothetical model inference inputs.

### `POST /predict`

Hypothetical resale-price prediction using the saved ridge pipeline; not for historical lookup and must surface defaulted inputs when present.

### `/rdd/summary`

High-level metadata about the school-specific RDD run, including coverage and bandwidth information.

### `/rdd/schools`

School-level coverage index showing which schools have successful RDD rows and which were skipped.

### `/rdd/results`

Main school-specific local premium endpoint containing sample sizes, premium percentages, SGD jumps, p-values, and confidence intervals.

### `/rdd/results/{school_name}`

Convenience endpoint for retrieving all school-specific RDD rows for one school.

### `/rdd/coefficients`

Full coefficient tables behind the school-specific RDD fits for deeper methodological inspection.

### `/rdd/group-comparison`

Pooled interaction-model result for whether local cutoff premiums differ between good and non-good schools; not a school-specific endpoint.

### `/rdd/group-comparison/coefficients`

Full coefficient table for the pooled good-vs-non-good interaction model.

### `/rdd/skipped`

Coverage and feasibility endpoint explaining which schools were excluded from school-specific RDD estimation and why.

### `/town-premiums/summary`

High-level summary of town-level premium outputs across all estimated towns.

### `/town-premiums`

Town-level premium estimates used to compare premium levels across towns; not a school-specific RDD endpoint.

### `/town-premiums/{town_name}`

Convenience endpoint for one town’s premium estimate.

### `/town-premiums/skipped`

Coverage endpoint explaining which towns were excluded from town-specific premium estimation and why.

### `/diagnostics/sign-trace`

Diagnostic endpoint showing how the `good_school_within_1km` coefficient changes as controls are added.

### `/benchmarks/summary`

Compact summary of the benchmark comparison, including best-performing variants by key metrics.

### `/benchmarks/results`

Full benchmark comparison table across predictive variants for model-selection and justification tasks.

### `/benchmarks/best`

Convenience endpoint for the best-performing benchmark variants by selected metrics.

### `/benchmarks/metadata`

Benchmark configuration and run metadata used to explain what was compared and under what setup.

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

## Tests

API endpoint tests live in [tests/test_api.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/tests/test_api.py).

Run them from the repository root with:

```powershell
python -m unittest discover -s tests -v
```

If your environment is set up through `uv`, you can also run:

```powershell
uv run python -m unittest discover -s tests -v
```
