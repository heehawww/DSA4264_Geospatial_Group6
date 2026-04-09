# DSA4264 Geospatial Group 6

This project studies how proximity to "good" primary schools is associated with HDB resale prices.

The technical report can be found [here](https://heehawww.github.io/DSA4264_Geospatial_Group6/technical_report/).

## Setup

If you are running locally, you can initialize a Python virtual environment and install the dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install .
```

Create a local `.env` file for chatbot configuration:

```env
OPENAI_API_KEY=<your_key_here>
OPENAI_MODEL=openai:gpt-4.1-mini
HDB_API_BASE_URL=http://127.0.0.1:8000
```

`HDB_API_BASE_URL` should point to the FastAPI backend. Use `http://127.0.0.1:8000` for local development.

Do not commit your real `.env` file because it can contain secrets.

## Data Layout

The repository now expects local data artifacts to be placed under the top-level `data/` directory, even if that directory is not pushed to GitHub.

Use this layout:

- `data/feature_engineering/inputs/`
  Place raw or upstream files used by the feature-engineering pipeline here.
  Typical examples include raw resale data, school scrape outputs, URA land-use files, HDB geometry layers, MRT or amenity GeoJSON files, and other external source files.

- `data/feature_engineering/intermediate/`
  Place temporary or partially processed geospatial join outputs here if you want to keep them between runs.
  This is for debugging and reproducibility, not for final downstream consumption.

- `data/feature_engineering/outputs/`
  Place the finalized feature-engineering outputs here.
  This is the canonical location for downstream modeling and frontend map data.
  The most important file here is:
  `data/feature_engineering/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv`

- `data/api/`
  Place the finalized API-served artifacts here.
  This folder is the canonical data source for the FastAPI backend.
  It should contain the files served by the API, such as:
  - raw resale data
  - model metrics
  - feature importance
  - OLS coefficients
  - ridge model artifact
  - school-specific RDD outputs
  - group-comparison outputs
  - town premium outputs
  - diagnostics
  - benchmark outputs
  - school lookup files used by `/schools/good`

In practice, the intended flow is:

1. Feature engineering produces local outputs under `data/feature_engineering/outputs/`
2. Hedonic-model and analysis scripts run from those canonical feature-engineering outputs
3. Final artifacts that need to be served by FastAPI are copied into `data/api/`

This means:

- the frontend map should read from `data/feature_engineering/outputs/`
- the hedonic-model scripts should read from `data/feature_engineering/outputs/`
- the FastAPI backend should read from `data/api/`

If you are setting up the project on a new machine, you should recreate the local `data/` directory and place the required files into the correct subfolders before running the pipeline, the API, or the frontend.

## Dataset Sources

The `data/` directory is not committed, so collaborators need to download the required source files locally and place them into the appropriate working folders before running the pipelines.

### Geospatial Data Used

| Feature | Description | Link |
|---|---|---|
| MRT Station Exits | A GeoJSON that provides vector coordinates of MRT station exits in Singapore. This is joined with a separate dataset containing MRT/LRT line information. | MRT locations: [data.gov.sg MRT dataset](https://data.gov.sg/datasets?query=MRT&resultId=d_b39d3a0871985372d7e1637193335da5) |
| MRT Lines | Dataset used to enrich MRT stations with line information. | [Kaggle MRT/LRT stations in Singapore](https://www.kaggle.com/datasets/lzytim/full-list-of-mrt-and-lrt-stations-in-singapore) |
| Bus Stops | A GeoJSON that provides vector coordinates of bus stop locations in Singapore. | [data.gov.sg bus stop locations](https://data.gov.sg/datasets/d_3f172c6feb3f4f92a2f47d93eed2908a/view) |
| Shopping Malls | A dataset that provides vector coordinates of shopping mall locations. | [Kaggle shopping mall coordinates](https://www.kaggle.com/datasets/karthikgangula/shopping-mall-coordinates) |
| Supermarkets | A GeoJSON that provides vector coordinates of supermarket locations in Singapore. | [data.gov.sg supermarket locations](https://data.gov.sg/datasets/d_cac2c32f01960a3ad7202a99c27268a0/view) |
| Hawker Centres | A GeoJSON that provides vector coordinates of NEA market and food centre locations in Singapore. | [data.gov.sg hawker centre locations](https://data.gov.sg/datasets/d_a57a245b3cf3ec76ad36d55393a16e97/view) |
| Parks | A GeoJSON that provides vector coordinates of parks in Singapore. | [data.gov.sg parks dataset](https://data.gov.sg/datasets/d_0542d48f0991541706b58059381a6eca/view) |
| URA Master Plan | A GeoJSON layer that provides vectorised land parcel designation. | [data.gov.sg URA Master Plan dataset](https://data.gov.sg/datasets?query=URA+master&resultId=d_90d86daa5bfaa371668b84fa5f01424f) |
| HDB Existing Buildings | A GeoJSON that provides vector objects for built HDB buildings. | [data.gov.sg HDB existing buildings dataset](https://data.gov.sg/datasets?query=HDB+building&resultId=d_16b157c52ed637edd6ba1232e026258d) |

These source datasets are primarily used in the feature-engineering stage. After downloading them, place them into the local working locations expected by the feature-engineering scripts, and then sync the resulting canonical outputs into:

- `data/feature_engineering/outputs/`
- `data/api/` for any final artifacts that the API must serve

## Running The Project By Module

Use the following modules in order, depending on what you need to regenerate.

### 1. Primary School Scrape

This step generates the local school subscription/source file used to classify good schools.

Expected local file:

- `primary_school_scrape/schools.csv`

Run from the repository root:

```bash
cd primary_school_scrape
scrapy crawl schools
```

This file is treated as a local generated artifact and is not meant to be committed.

### 2. Feature Engineering

This step generates school-boundary features, address-point coverage outputs, and the walkability-enriched resale feature table.

Inputs should be organized under:

- `data/feature_engineering/inputs/`

Canonical outputs should end up under:

- `data/feature_engineering/outputs/`

Run from the repository root:

```bash
python -m feature_engineering.main sync-outputs
```

Or run individual steps:

```bash
python -m feature_engineering.main run-step build_primary_school_boundaries
python -m feature_engineering.main run-step classify_good_schools
```

The main downstream file produced by this module is:

- `data/feature_engineering/outputs/resale_flats_with_school_buffer_counts_with_walkability.csv`

### 3. Hedonic Model And Analysis

This step trains the predictive model and generates RDD, town-premium, diagnostic, and benchmark outputs.

It reads from:

- `data/feature_engineering/outputs/`

Key scripts include:

- `hedonic_model/train_hedonic_model.py`
- `hedonic_model/run_school_boundary_rdd.py`
- `hedonic_model/run_town_premium_models.py`
- `hedonic_model/trace_school_premium_sign.py`
- `hedonic_model/benchmark_hedonic_variants.py`

After running these scripts, copy the final artifacts needed by the API into:

- `data/api/`

### 4. FastAPI Backend

The backend expects its served artifacts under:

- `data/api/`

This includes all files used by:

- `/resales/*`
- `/model/*`
- `/predict`
- `/schools/good`
- `/rdd/*`
- `/town-premiums/*`
- `/diagnostics/*`
- `/benchmarks/*`

Start the API from the repository root:

```bash
uvicorn api.main:app --reload
```

### 5. Streamlit Frontend

The frontend uses both:

- `data/feature_engineering/outputs/` for map layers and map-facing data
- the FastAPI backend for analytical chatbot responses

Start the frontend from the repository root:

```bash
streamlit run app.py
```

If the backend is not running, the map can still render, but the chatbot will fall back to limited local responses.

## Run the Frontend

From the repository root, activate the virtual environment and start the Streamlit app:

```bash
source venv/bin/activate
streamlit run app.py
```

The frontend has two tabs:

- `Map`: shows resale flats, school 1km/2km boundaries, and HDB building outlines.
- `Chatbot`: answers questions about the current map filters and model outputs.

For the service-backed chatbot, start the FastAPI backend in a separate terminal before using the chatbot:

```bash
source venv/bin/activate
uvicorn api.main:app --reload
```

If the API is not running, the map still works, but the chatbot will show that the API is offline.

## Run With Docker

From the repository root, build and start both the FastAPI backend and Streamlit frontend:

```bash
docker compose up --build
```

Then open:

- Streamlit frontend: `http://localhost:8501`
- FastAPI docs: `http://localhost:8000/docs`

If you want to use the LLM-backed chatbot, pass your OpenAI API key when starting Docker:

```bash
OPENAI_API_KEY=your_key_here docker compose up --build
```

Inside Docker Compose, the frontend automatically uses `HDB_API_BASE_URL=http://api:8000` so it can reach the API container.

The Docker setup expects the same data artifacts used by the local app to be present in the repo before building.
