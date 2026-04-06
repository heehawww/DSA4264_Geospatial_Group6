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

From the repository root, the recommended predictive run is:

```bash
python3 hedonic_model/train_hedonic_model.py \
  --feature-spec reduced \
  --rebalance-floor-area \
  --output-dir hedonic_model/rebalanced_outputs
```

Optional arguments:

```bash
python3 hedonic_model/train_hedonic_model.py \
  --input-csv "walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv" \
  --output-dir hedonic_model/outputs \
  --test-months 12 \
  --feature-spec reduced \
  --rebalance-floor-area
```

Feature specs:

- `baseline`: original richer predictive feature set
- `reduced`: pruned feature set that removes the most redundant time, lease, and school indicators for a lower-multicollinearity predictive model. This is the default and preferred predictive spec.

Optional predictive rebalancing:

- `--rebalance-floor-area`: upsamples underrepresented `floor_area_sqm` bands before fitting the Ridge model. This is the preferred predictive configuration.
- `--weight-floor-area`: upweights underrepresented `floor_area_sqm` bands without duplicating rows
- `--rebalance-bins`: number of quantile bins used for rebalancing, default `8`
- `--rebalance-target-fraction`: target quantile of bin size to rebalance toward, default `0.75`

## Outputs

The script writes to `hedonic_model/outputs/`:

- `metrics.json`
- `feature_importance_top.csv`
- `ols_coefficients.csv`
- `model_summary.txt`

When floor-area rebalancing is enabled, `metrics.json` also records the predictive training row count after rebalancing and the rebalance settings used.

## Interpretation

The main policy-facing term is `good_school_within_1km`, derived from `good_school_count_1km > 0`.

Because the dependent variable is `log(resale_price)`, the approximate percentage premium is:

`exp(beta) - 1`

for a binary indicator coefficient `beta`.

## Boundary RDD

A separate script estimates school-specific local linear regression-discontinuity designs around each primary school's `1km` cutoff:

```bash
python3 hedonic_model/run_school_boundary_rdd.py
```

Default inputs:

- `walking time to nearest xx/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv`
- `primary_boundaries/outputs/resale_address_points_matched_with_school_counts.geojson`
- `primary_boundaries/outputs/primary_school_boundaries_buffer_1km.geojson`

Default outputs in `hedonic_model/rdd_outputs/`:

- `school_specific_rdd_results.csv`
- `school_specific_rdd_coefficients.csv`
- `school_specific_rdd_skipped.csv`
- `school_specific_address_signed_distances.csv`
- `rdd_summary.json`

The running variable is the signed distance in meters from an HDB address point to each school's `1km` buffer boundary:

- negative: inside the `1km` catchment
- positive: outside the `1km` catchment

The script reports school-specific results at each bandwidth for:

- `uncontrolled`
- `controlled`

This is a useful local design, but it is still approximate because the project uses address points rather than exact unit locations.

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

## Model Benchmarks

To compare feature-reduction and regression variants for the predictive hedonic model:

```bash
python3 hedonic_model/benchmark_hedonic_variants.py
```

Outputs in `hedonic_model/benchmark_outputs/`:

- `benchmark_results.csv`
- `benchmark_results.json`
- `benchmark_metadata.json`

Benchmarked variants include:

- Ridge with baseline features
- Ridge with reduced features
- Ridge with VIF-pruned features
- Ridge with `f_regression` numeric selection
- Lasso
- Elastic Net
- floor-area-bin rebalanced Ridge
- floor-area-bin weighted Ridge

Note: classic SMOTE is not used here because this is a regression problem with a continuous target. The benchmark uses a simpler floor-area rebalancing baseline instead.
