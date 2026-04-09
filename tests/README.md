# API Tests

This directory contains integration-style tests for the finalized FastAPI endpoints.

The tests use the real FastAPI app in `api.main` and exercise:

- system endpoints
- resale endpoints
- model endpoints
- prediction endpoints
- RDD endpoints
- town premium endpoints
- diagnostics endpoints
- benchmark endpoints

Run them from the repository root with:

```powershell
python -m unittest discover -s tests -v
```

If you are using `uv`, you can also run:

```powershell
uv run python -m unittest discover -s tests -v
```

There is also a dedicated integration suite in [tests/test_api_integration.py](/Users/tjiay/Documents/NUS/DSA4264_Geospatial_Group6/tests/test_api_integration.py) for cross-endpoint workflow checks.
