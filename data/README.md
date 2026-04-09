Shared project data layout.

Top-level structure:

- `api/`: finalized artifacts served by the FastAPI backend
- `feature_engineering/`: shared data layout for the feature-engineering pipeline

How they are used:

- API resale endpoints: `api/resale_flat_prices.csv`
- API prediction defaults and feature engineering: `api/resale_flats_with_school_buffer_counts_with_walkability.csv`
- API model endpoints: `api/metrics.json`, `api/feature_importance_top.csv`, `api/ols_coefficients.csv`, `api/ridge_pipeline.pkl`
- API RDD endpoints: `api/school_specific_rdd_results.csv`, `api/school_specific_rdd_coefficients.csv`, `api/school_specific_rdd_skipped.csv`, `api/school_group_interaction_results.csv`, `api/school_group_interaction_coefficients.csv`, `api/rdd_summary.json`
- API town premium endpoints: `api/town_premium_results.csv`, `api/town_premium_skipped.csv`
- API diagnostics endpoints: `api/good_school_sign_trace.csv`
- API benchmark endpoints: `api/benchmark_results.csv`, `api/benchmark_results.json`, `api/benchmark_metadata.json`
