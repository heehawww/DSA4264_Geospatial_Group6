# Hedonic Model

This module trains a baseline hedonic resale-price model from the preprocessed feature table produced on the `Data-Preprocessing` branch.

## Input dataset

Default input:

`walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv`

The script expects the following groups of columns:

- structural HDB features
  - `floor_area_sqm`
  - `flat_type`
  - `flat_model`
  - `storey_range`
  - `lease_commence_date`
  - `remaining_lease`
- time and location controls
  - `month`
  - `town`
- school exposure variables
  - `school_count_1km`
  - `good_school_count_1km`
  - `school_count_2km`
  - `good_school_count_2km`
- amenity and accessibility variables
  - walking-distance columns
  - amenity count columns

## Model design

The baseline model predicts `log(resale_price)` using:

- structural features
- town fixed effects
- transaction month fixed effects
- amenity access variables
- school-exposure variables

It fits two models:

1. `Ridge` regression for stable out-of-sample prediction with one-hot encoded categorical variables
2. `OLS` for interpretable coefficients on the engineered covariates

## Run

From the repository root:

```bash
python3 hedonic_model/train_hedonic_model.py
```

Optional arguments:

```bash
python3 hedonic_model/train_hedonic_model.py \
  --input-csv "walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv" \
  --output-dir hedonic_model/outputs \
  --test-months 12 \
  --feature-spec reduced
```

Feature specs:

- `baseline`: original richer predictive feature set
- `reduced`: pruned feature set that removes the most redundant time, lease, and school indicators for a lower-multicollinearity predictive model

## Outputs

The script writes to `hedonic_model/outputs/`:

- `metrics.json`
- `feature_importance_top.csv`
- `ols_coefficients.csv`
- `model_summary.txt`

## Interpretation

The main policy-facing term is `good_school_within_1km`, derived from `good_school_count_1km > 0`.

Because the dependent variable is `log(resale_price)`, the approximate percentage premium is:

`exp(beta) - 1`

for a binary indicator coefficient `beta`.

## Boundary RDD

A separate script estimates a local linear regression-discontinuity design around the `1km` good-school cutoff:

```bash
python3 hedonic_model/run_school_boundary_rdd.py
```

Default inputs:

- `walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv`
- `primary_boundaries/outputs/resale_address_points_matched_with_school_counts.geojson`
- `primary_boundaries/outputs/primary_school_boundaries_buffer_1km.geojson`

Default outputs in `hedonic_model/rdd_outputs/`:

- `rdd_results.csv`
- `rdd_coefficients.csv`
- `address_signed_distances.csv`
- `rdd_summary.json`

The running variable is the signed distance in meters from an HDB address point to the nearest good school's `1km` buffer boundary:

- negative: inside the `1km` catchment
- positive: outside the `1km` catchment

The script reports three specifications at each bandwidth:

- `uncontrolled`
- `controlled`
- `school_fe` for a controlled local regression with school fixed effects

This is a useful local design, but it is still approximate because the project uses address points rather than exact unit locations and pools multiple school markets together.

## Coefficient Trace

To see when the `good_school_within_1km` coefficient changes sign as controls are added:

```bash
python3 hedonic_model/trace_school_premium_sign.py
```

Outputs in `hedonic_model/diagnostic_outputs/`:

- `good_school_sign_trace.csv`
- `good_school_sign_trace.json`

## Town-Specific Premium Models

To estimate the clean `good_school_count_1km` premium separately by town:

```bash
python3 hedonic_model/run_town_premium_models.py
```

Outputs in `hedonic_model/town_outputs/`:

- `town_premium_results.csv`
- `town_premium_skipped.csv`
- `town_premium_results.json`
