Finalized API data directory.

These files are currently used by the API in `api/`:

- `resale_flat_prices.csv`
- `resale_flats_with_school_buffer_counts_with_walkability.csv`
- `metrics.json`
- `feature_importance_top.csv`
- `ols_coefficients.csv`
- `ridge_pipeline.pkl`
- `school_specific_rdd_results.csv`
- `school_specific_rdd_coefficients.csv`
- `school_specific_rdd_skipped.csv`
- `school_group_ttests.csv`
- `rdd_summary.json`
- `town_premium_results.csv`
- `town_premium_skipped.csv`
- `good_school_sign_trace.csv`
- `benchmark_results.csv`
- `benchmark_results.json`
- `benchmark_metadata.json`

How they are used:

- resale endpoints: `resale_flat_prices.csv`
- prediction defaults and feature engineering: `resale_flats_with_school_buffer_counts_with_walkability.csv`
- model endpoints: `metrics.json`, `feature_importance_top.csv`, `ols_coefficients.csv`, `ridge_pipeline.pkl`
- RDD endpoints: `school_specific_rdd_results.csv`, `school_specific_rdd_coefficients.csv`, `school_specific_rdd_skipped.csv`, `school_group_ttests.csv`, `rdd_summary.json`
- town premium endpoints: `town_premium_results.csv`, `town_premium_skipped.csv`
- diagnostics endpoints: `good_school_sign_trace.csv`
- benchmark endpoints: `benchmark_results.csv`, `benchmark_results.json`, `benchmark_metadata.json`
