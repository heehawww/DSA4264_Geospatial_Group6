# DSA4264 Geospatial Group 6

This project studies how proximity to "good" primary schools is associated with HDB resale prices.

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
