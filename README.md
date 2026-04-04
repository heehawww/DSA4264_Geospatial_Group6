# DSA4264 Geospatial Group 6

This project studies how proximity to "good" primary schools is associated with HDB resale prices.

The current FastAPI app is designed as a data-and-model backend for a separate agentic chat layer. The API does not decide intent for the LLM. Instead, it exposes distinct endpoints for:

- historical records and summaries
- model interpretation outputs
- aggregated RDD outputs
- model-generated predictions

That separation is important because some outputs are descriptive, some are model-based, and some are quasi-experimental.

## System Context

The API currently loads its artifacts from [data/README.md](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/data/README.md).

These files come from three main pipelines:

- Hedonic model outputs from [hedonic_model/README.md](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/hedonic_model/README.md)
- Boundary RDD outputs from `hedonic_model/run_school_boundary_rdd.py`
- Flat-level premium scoring outputs from `hedonic_model/score_school_premium.py`

The key source table used across the modeling pipeline is:

- `data/resale_flats_with_school_buffer_counts_with_walkability.csv`

This is not a raw resale file. It is a processed feature table that already includes:

- HDB resale transaction attributes
- school count features within `1km` and `2km`
- amenity walking-distance features
- amenity count features

The saved predictive model is:

- `data/ridge_pipeline.pkl`

This ridge model predicts `log(resale_price)` and is used for `POST /predict`.

The saved interpretable coefficient table is:

- `data/ols_coefficients.csv`

This OLS table is used for coefficient lookup and interpretation.

The RDD outputs are aggregated pooled results around the `1km` good-school boundary:

- `data/rdd_results.csv`
- `data/rdd_summary.json`

The premium outputs are transaction-level scored rows for treated flats only:

- `data/flat_school_premiums_treated_only.csv`
- `data/scoring_summary.json`

## Important Interpretation Rules

The next person working on the chat layer should preserve these distinctions:

- `/resales/*` endpoints are observed dataset endpoints
- `/ols/*` endpoints are model interpretation endpoints
- `/rdd/*` endpoints are aggregated discontinuity-study endpoints
- `/predict` is a model inference endpoint
- `/premiums*` endpoints are model-scored premium outputs, not observed premiums

This means:

- if the user asks what happened in the historical data, use `/resales/*`
- if the user asks what the regression coefficient is, use `/ols/*`
- if the user asks about the boundary design or discontinuity estimates, use `/rdd/*`
- if the user asks for a hypothetical price for a flat specification, use `/predict`
- if the user asks for the estimated school premium attached to scored transactions, use `/premiums*`

The LLM should not answer a historical query with `/predict`, and should not answer a hypothetical query with `/resales/raw`.

## Endpoint Guide

### `GET /metadata`

Use this as the first diagnostic endpoint.

It reports:

- which datasets are loaded
- row counts
- model metrics
- RDD summary metadata
- premium summary metadata
- whether the true raw resale CSV is available

This is the best endpoint for the chat layer to call when it needs to know whether `data/resale_hdbs_raw.csv` exists.

### `GET /ols/coefficients`

Use this when the user asks for regression coefficients or wants to search for a term such as:

- `good_school_within_1km`
- `floor_area_sqm`
- a specific town fixed effect

This endpoint returns rows from the OLS coefficient table produced by the hedonic model.

How it was derived:

- the training script engineers features from the processed feature table
- it fits an OLS model on `log_resale_price`
- the exported statsmodels coefficient table is written to `ols_coefficients.csv`

This endpoint is for interpretation, not prediction.

### `GET /ols/coefficients/{term}`

Use this when the chat layer already knows the exact term name and wants a single coefficient row.

### `GET /model/metrics`

Returns the saved ridge train/test metrics and the OLS-derived school premium summary from `metrics.json`.

This is useful when the user asks:

- how well the model performs
- what the held-out `R^2`, RMSE, or MAE is

### `GET /rdd/summary`

Returns metadata about the RDD run, such as:

- number of transaction rows used
- number of geocoded addresses
- number of good-school buffers
- bandwidths evaluated

This is not the place to answer coefficient or jump-size questions. Use `/rdd/results` for that.

### `GET /rdd/results`

Returns aggregated pooled RDD result rows, filterable by:

- `specification`
- `bandwidth_m`

How it was derived:

- the script computes signed distances from HDB address points to the nearest good-school `1km` boundary
- it estimates local linear weighted regressions at several bandwidths
- it exports pooled summary rows across specifications and bandwidths

Important caveats for the chat layer:

- this is an aggregated pooled RDD, not school-specific RDD right now
- the running variable is based on address points, not exact unit locations
- this design pools multiple school markets together

If the user asks for school-specific RDD results, the agent should be upfront that the API currently only exposes aggregated pooled results.

### `GET /premiums/summary`

Returns overall summary statistics for the scored premium dataset.

How it was derived:

- the premium scoring script predicts each treated flat's price using the fitted hedonic model
- it builds a counterfactual with `good_school_count_1km = 0` and `good_school_within_1km = 0`
- the estimated premium is the difference between the two predictions

This is an associated model premium, not a causal flat-level treatment effect.

### `GET /premiums`

Returns transaction-level scored premium rows with filters such as:

- `town`
- `flat_type`
- premium range

This is best when the user asks:

- show me examples of scored premiums
- list treated flats in a town
- what are the premiums for these types of flats

These rows come from `flat_school_premiums_treated_only.csv`, so they are treated flats only.

### `GET /resales/raw`

Returns row-level JSON records for the resale dataset used by the API.

Behavior:

- if `data/resale_hdbs_raw.csv` exists, this endpoint should serve the true raw resale file
- if it does not exist, the endpoint currently falls back to the processed feature table and says so explicitly

The response includes an `is_true_raw_dataset` flag so the chat layer can avoid overstating what it is looking at.

This endpoint is for record retrieval, not aggregation.

### `GET /resales/summary`

Returns aggregated resale statistics over the dataset currently backing `/resales/raw`.

Supported use cases:

- median resale price in a town
- mean resale price for a flat type
- combined summary for multiple towns
- split summaries using `group_by=town|flat_type|month`

Important chat behavior:

- if the user says "Tampines and Bedok", the agent can query both towns together
- if the user wants them broken out separately, the agent should pass `group_by=town`
- if `group_by` is omitted, the endpoint returns one combined aggregate over all matched rows

This is the main endpoint for historical aggregation questions.

### `GET /predict/schema`

This endpoint helps the chat layer understand the inference contract.

It returns:

- accepted raw request fields for `/predict`
- engineered model fields used internally
- the defaults used when fields are omitted
- sample allowed categories

The agent layer should use this endpoint as a contract reference if it needs to explain what can be provided by the user.

### `POST /predict`

This is the model inference endpoint for hypothetical flats.

How it works:

1. The API accepts a raw flat specification such as:
   `month`, `town`, `flat_type`, `flat_model`, `floor_area_sqm`, `remaining_lease`, `storey_range`, school counts, and amenity distances/counts.
2. Missing values are filled using dataset-backed defaults from the processed feature table.
3. The API engineers the exact features expected by the saved ridge pipeline.
4. The ridge model predicts `log_resale_price`.
5. The API exponentiates the prediction and returns the predicted SGD price.

The response includes:

- `predicted_price`
- `engineered_features_used`
- `defaulted_raw_fields`

Important chat behavior:

- if only a few fields were provided, the LLM should clearly tell the user that many other fields were defaulted
- if the user asks what can be provided, the LLM should refer to `/predict/schema`
- this endpoint is for hypothetical estimation, not for looking up an observed transaction

## How The Chat Layer Should Choose Endpoints

Here is the practical routing logic for the future agent:

- "What was the median resale price in Tampines?" -> `GET /resales/summary`
- "Show me some resale records in Bedok" -> `GET /resales/raw`
- "What is the coefficient on good_school_within_1km?" -> `GET /ols/coefficients/good_school_within_1km`
- "What are the RDD results at 300m?" -> `GET /rdd/results?bandwidth_m=300`
- "What premiums were estimated for treated flats in Ang Mo Kio?" -> `GET /premiums?town=ANG MO KIO`
- "Predict the price of this flat" -> `POST /predict`

The clean distinction is:

- observed past data -> `/resales/*`
- modeled relationship summaries -> `/ols/*`, `/rdd/*`, `/premiums*`
- hypothetical price estimation -> `/predict`

## How This Works In Chat

The intended chat flow is:

1. User asks a question in natural language.
2. The agent decides whether the question is:
   - historical lookup
   - historical aggregation
   - model interpretation
   - RDD interpretation
   - premium lookup
   - hypothetical prediction
3. The agent calls the matching API endpoint.
4. The agent answers in plain language and preserves the right caveats.

Examples:

- If the user asks "What is the median resale price in Tampines and Bedok?"
  The agent should use `/resales/summary` with both towns.
  If the user wants a combined answer, do not set `group_by`.
  If the user wants a split answer, set `group_by=town`.

- If the user asks "How much would this flat cost?"
  The agent should use `/predict`.
  If many fields are missing, the agent should say the prediction used defaulted inputs.

- If the user asks "What is the school premium?"
  The agent must first determine whether they mean:
  - the OLS average coefficient interpretation
  - the RDD discontinuity result
  - the model-scored flat-level premiums
  If unclear, the agent should clarify that there are multiple notions of "premium" in this system.

## Known Gaps And Context Still Missing

These parts are still not fully documented from the current workspace alone:

- the final provenance and schema of the true raw resale CSV that should live at `data/resale_hdbs_raw.csv`
- the exact business definition of "good" primary school beyond the derived flags present in the modeling outputs
- whether any endpoint should expose GeoJSON or map-ready outputs in the final product
- whether the chat layer should prefer pooled RDD results or a single default specification/bandwidth when the user asks a vague RDD question

If those decisions matter for the final agent prompt, the next developer should confirm them with the team rather than infer them.

## Running The Modeling Scripts

Install dependencies first.

Train the hedonic model:

```bash
python3 hedonic_model/train_hedonic_model.py
```

Run the RDD script:

```bash
python3 hedonic_model/run_school_boundary_rdd.py
```

Score flat-level premiums:

```bash
python3 hedonic_model/score_school_premium.py
```
