# DSA4264 Geospatial Group 6

This project studies how proximity to "good" primary schools is associated with HDB resale prices.

## Setup

If you are running locally, you can initialize a Python virtual environment and install the dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install .
```

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
