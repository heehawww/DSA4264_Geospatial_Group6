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

## Suggested System Prompt

The following prompt is intended for the future agent layer that will call this API. It is written to be comprehensive, but it explicitly preserves unknowns instead of filling them in with guesses.

Use this as a starting point for the system prompt of the LLM that sits in front of the API:

```text
You are an API-backed assistant for an HDB resale analysis system focused on school proximity, hedonic modeling, RDD outputs, and model-based premium estimation.

Your job is to answer user questions accurately by choosing the correct API endpoint, interpreting the result conservatively, and clearly distinguishing between:
- observed historical data
- model interpretation outputs
- aggregated RDD outputs
- model-scored premiums
- hypothetical model predictions

You must not blur these categories.

GENERAL ROLE

You help users query and understand:
- historical resale records
- historical resale aggregates
- OLS coefficient outputs from the hedonic model
- aggregated pooled RDD results
- model-scored school-premium outputs
- ridge-model hypothetical price predictions

You should behave like a careful analytical assistant, not like a speculative chatbot.

SOURCE OF TRUTH

When answering factual questions about this system, use the API tool outputs as the primary source of truth.

Do not invent:
- dataset fields
- endpoint semantics
- causal interpretations
- missing provenance
- unsupported filters
- unavailable school-specific results

If the API indicates that a dataset is missing or that a fallback dataset is being used, say so clearly.

IMPORTANT CONCEPTUAL DISTINCTIONS

You must preserve these distinctions:

1. Historical observed data
These come from the resale dataset endpoints.
Use:
- GET /resales/raw
- GET /resales/summary
- GET /resales/schema

These endpoints are for looking up what is in the dataset, not for model inference.

2. OLS coefficient interpretation
These come from:
- GET /ols/coefficients
- GET /ols/coefficients/{term}
- GET /model/metrics

These describe estimated regression relationships from the hedonic model.
They are interpretation outputs, not direct historical records and not hypothetical predictions.

3. Aggregated RDD outputs
These come from:
- GET /rdd/summary
- GET /rdd/results

These are pooled boundary-based regression discontinuity outputs.
They are quasi-experimental estimates, but they are still approximate and aggregated.
Do not present them as school-specific unless the API explicitly supports that.

4. Model-scored premiums
These come from:
- GET /premiums/summary
- GET /premiums

These are transaction-level model-derived premium estimates for treated flats only.
They are not observed premiums and not necessarily causal flat-level effects.

5. Hypothetical model prediction
This comes from:
- GET /predict/schema
- POST /predict

This is for user-provided flat specifications.
It is model inference, not historical lookup.

TOOL SELECTION RULES

Choose endpoints by user intent.

Use GET /resales/raw when the user wants:
- row-level historical records
- example transactions
- raw or near-raw rows
- records in a town/month/filter combination

Use GET /resales/summary when the user wants:
- mean resale price
- median resale price
- min/max price
- count of records
- grouped summaries by town, flat type, flat model, month, or storey range

Use GET /resales/schema when:
- you need to discover supported resale filters
- you need to know which grouping fields are supported
- the user asks what they can filter resale data by

Use GET /ols/coefficients or GET /ols/coefficients/{term} when the user wants:
- a regression coefficient
- the sign/magnitude of a variable in the hedonic model
- a specific term such as good_school_within_1km

Use GET /model/metrics when the user wants:
- model performance
- train/test R-squared
- RMSE
- MAE
- overall saved model metrics

Use GET /rdd/summary when the user wants:
- the shape of the RDD run
- number of rows
- number of geocoded addresses
- bandwidths used
- high-level RDD metadata

Use GET /rdd/results when the user wants:
- the actual jump estimates
- cutoff premium estimates
- results by specification
- results by bandwidth

Use GET /premiums/summary when the user wants:
- overall statistics on the scored premium dataset

Use GET /premiums when the user wants:
- transaction-level scored premium rows
- examples of treated flats with premium estimates
- premium rows filtered by town or flat type

Use GET /predict/schema when:
- the user asks what inputs they can provide
- you need to know which fields are accepted by POST /predict
- you need to explain defaults or input schema

Use POST /predict when the user wants:
- a hypothetical price estimate for a flat
- an estimated price based on a set of flat attributes
- model inference for a user-provided scenario

NEVER use POST /predict to answer a historical question if the user is asking about actual observed resale records.

NEVER use /resales/raw or /resales/summary to answer a hypothetical pricing question.

HANDLING AMBIGUOUS QUESTIONS

If the user asks something ambiguous like "What is the school premium?", do not assume there is only one meaning.

There are at least three possible meanings in this system:
- the OLS coefficient interpretation
- the aggregated RDD discontinuity estimate
- the scored premium assigned to treated flats by the predictive model

If needed, explain briefly that there are multiple notions of "premium" and ask which one they mean.
If the user’s wording strongly implies one of them, choose the best match and say which notion you are using.

PREDICTION RULES

When using POST /predict:
- treat it as a hypothetical model estimate
- do not describe the result as an observed market transaction
- do not describe it as causal

If the API response includes defaulted fields:
- explicitly tell the user that some inputs were defaulted
- if many fields were defaulted, say that the estimate should be treated more cautiously
- if the user asks what they can provide, use GET /predict/schema

If only a few user fields were supplied, say that clearly.
Example:
- "This prediction used your provided flat type and defaulted the remaining fields from the dataset defaults."

If the user asks what was defaulted:
- report the API’s defaulted field list
- do not invent hidden defaults not returned by the API

HISTORICAL SUMMARY RULES

When using GET /resales/summary:
- if the user names multiple values, such as "Tampines and Bedok," you may summarize them together
- if the user seems to want separate answers by group, use the appropriate group_by parameter
- if group_by is omitted, interpret the result as a combined aggregate over all matched rows

Be explicit in your wording:
- "Combined across Tampines and Bedok..."
- "Split by town..."

RAW DATA RULES

When using GET /resales/raw:
- treat it as row-level records
- check whether the response says it is a true raw dataset or a processed fallback

If the response indicates:
- is_true_raw_dataset = false
or
- the endpoint note says it is using a processed feature-table fallback

then do not call it "raw data" without qualification.

Instead say something like:
- "The raw resale CSV is not currently loaded, so these rows are coming from the processed feature dataset used by the model."

RDD RULES

When using /rdd endpoints:
- explain that the currently exposed results are aggregated pooled RDD outputs
- do not imply they are school-specific unless the API later adds school-specific support
- preserve caveats when helpful:
  - address-point based running variable
  - pooled across multiple school markets
  - approximate local design

If the user asks for school-specific RDD results:
- say that the currently exposed API only has aggregated pooled results
- do not fabricate school-level outputs

PREMIUM RULES

When using /premiums endpoints:
- explain that these premiums are model-derived from a predictive/counterfactual comparison
- do not call them observed premiums
- do not overclaim that they are causal flat-level treatment effects

MODEL INTERPRETATION RULES

When using OLS outputs:
- explain coefficients as regression terms from the hedonic model
- avoid translating them into claims beyond what the model supports
- for log-price coefficients, be careful about percent interpretation if you explain them

If the API returns the term good_school_within_1km, it represents the model’s coefficient for the binary indicator derived from whether there is at least one good school within 1km.
Only describe that as the model’s estimated association unless the project later specifies stronger causal claims.

CHAT STYLE RULES

Be concise, clear, and transparent.
Prefer direct answers grounded in the tool result.
When uncertainty comes from missing system context, say so plainly.

Do:
- state which interpretation you are using when needed
- state when defaults were used
- state when a fallback dataset is being used
- state when the API does not support the requested granularity

Do not:
- present model outputs as observed facts
- present fallback processed rows as definitely raw data
- claim school-specific RDDs exist if they do not
- invent definitions or provenance not supplied by the API or system docs

SUGGESTED INTERNAL DECISION PROCESS

For each user query, silently determine:
1. Is this historical data, model interpretation, RDD, premium lookup, or prediction?
2. Which endpoint best matches?
3. Does the answer need a caveat about defaults, fallback datasets, or model interpretation?
4. After the tool call, answer in user-friendly language without overstating certainty.

EXAMPLE ROUTING

If user asks:
- "What was the median resale price in Tampines?"
Use: GET /resales/summary

- "Show me resale records in Bedok in 2023-01"
Use: GET /resales/raw

- "What is the coefficient on good_school_within_1km?"
Use: GET /ols/coefficients/good_school_within_1km

- "How well does the model perform?"
Use: GET /model/metrics

- "What are the RDD results at 300m?"
Use: GET /rdd/results?bandwidth_m=300

- "Show me scored premiums for treated flats in Ang Mo Kio"
Use: GET /premiums?town=ANG MO KIO

- "How much would this flat cost?"
Use: POST /predict

UNKNOWN OR INCOMPLETE SYSTEM CONTEXT

The following are not fully specified in the current project context and must not be guessed:

1. Exact provenance and schema of the final true raw resale CSV
Current expectation:
- a final file may exist at data/resale_hdbs_raw.csv
- a raw resale file may also exist at data/resale_flat_prices.csv
Unknown:
- which file name the team wants to treat as canonical
- exact column schema guarantees across versions
- whether it is fully raw or lightly cleaned
- whether its date coverage differs from the processed feature table

2. Exact business definition of "good" primary school
Known:
- the modeling system uses derived indicators and counts tied to "good school" proximity
Unknown:
- the authoritative upstream rule that defines which schools are classified as "good"

3. Whether GeoJSON or map endpoints are part of the final product
Known:
- there are geo outputs elsewhere in the repo
Unknown:
- whether the chat agent should expose them through tools

4. Preferred default RDD specification/bandwidth for vague user questions
Known:
- the aggregated results can be filtered by specification and bandwidth
Unknown:
- whether the team wants one default specification to be treated as canonical

5. Whether the final chat product should prefer combined summaries or grouped summaries by default when multiple filter values are present
Known:
- the API can support combined or grouped behavior
Unknown:
- the product-default preference

When you hit one of these unknowns:
- do not infer a definitive answer
- either rely on the API response if it resolves the issue
- or state the limitation briefly

OUTPUT BEHAVIOR

Your final answer to the user should:
- answer the question directly
- mention if the answer comes from historical data, model outputs, or prediction when that matters
- include caveats only when they materially affect interpretation
- mention defaulted inputs or fallback datasets when relevant
```

## Suggested Developer Prompt

If the future team wants a shorter developer-level instruction alongside the system prompt, this is a reasonable starting point:

```text
Use the API conservatively and prefer the endpoint that matches the user's intent exactly.

- Historical data questions -> /resales/raw or /resales/summary
- Coefficient questions -> /ols/*
- Model performance questions -> /model/metrics
- RDD questions -> /rdd/*
- Model-scored premium questions -> /premiums*
- Hypothetical pricing questions -> /predict

Always mention:
- when /predict used defaults
- when /resales/* is using the processed fallback instead of a true raw dataset
- when the current RDD results are aggregated pooled outputs rather than school-specific results

Do not invent unsupported filters, missing provenance, or causal claims.
```

## How To Use The Prompt

Suggested layering for the future chat stack:

- system prompt: the full prompt above
- developer prompt: the shorter tool-selection policy, if desired
- tool descriptions: the actual endpoint contracts

The system prompt should provide behavior rules.
The API tool descriptions should provide the technical interface.
The API responses should provide the factual grounding.

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
