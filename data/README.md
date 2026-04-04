API data directory.

Files currently expected by `api/data.py`:

- `resale_flats_with_school_buffer_counts_with_walkability.csv`
- `ols_coefficients.csv`
- `metrics.json`
- `ridge_pipeline.pkl`
- `rdd_results.csv`
- `rdd_summary.json`
- `flat_school_premiums_treated_only.csv`
- `scoring_summary.json`

Optional file for the final API:

- `resale_hdbs_raw.csv`

If `resale_hdbs_raw.csv` is missing, the API falls back to the processed feature table for `/resales/raw` and `/resales/summary`, and reports that clearly in its metadata and response notes.
