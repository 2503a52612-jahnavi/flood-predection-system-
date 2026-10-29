# Floodcast

Floodcast explores reported flood impacts across Indian States and Union Territories. The included cleaned dataset contains **105 state/UT-year records** for **2016–2018**. This project presents historical impact analysis; it does not forecast floods or predict future impacts.

## What is included

- `datacleaning.py` — cleans the source CSV with pandas.
- `RS_Session_250_AU86_Annexure-II.csv` — source CSV supplied with the project.
- `CLEAN_FLOOD_DATA_CLEANED.csv` — cleaned CSV used by the Streamlit app.
- `app.py` — Streamlit dashboard with year/state filters, impact summaries, interactive charts, a searchable records table, and CSV export.
- `DAV(j).ipynb` and `data_analysis (3).ipynb` — project notebooks with exploratory analysis and charts.
- `backend/` and `frontend/` — FastAPI API and React/Vite dashboard.
- `data/CLEAN_FLOOD_DATA_CLEANED.csv` — cleaned CSV loaded by the FastAPI backend.

## Data cleaning

From the repository root, activate your Python environment, install the dependencies, then run:

```powershell
python datacleaning.py
```

The script reads `RS_Session_250_AU86_Annexure-II.csv` and writes `CLEAN_FLOOD_DATA_CLEANED.csv` beside the script. It trims surrounding whitespace, excludes annual `Total` summary rows, removes exact duplicate rows, converts `Nil` to zero, preserves blank/`NA` numeric values as missing, and validates numeric fields. It stops with an error rather than silently dropping records when it encounters unexpected values.

The script updates the root CSV used by Streamlit. To update the copy used by the FastAPI app as well, run:

```powershell
Copy-Item .\CLEAN_FLOOD_DATA_CLEANED.csv .\data\CLEAN_FLOOD_DATA_CLEANED.csv -Force
```

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer with npm (for the React frontend)

## Run the Streamlit dashboard

From the repository root, open PowerShell and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL in the terminal, usually <http://localhost:8501>.

## Run the React and FastAPI dashboard

Run the backend and frontend in separate terminals. Start both terminals in the repository root.

### 1. Start the API

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The API is at <http://127.0.0.1:8000>. Interactive API documentation is at <http://127.0.0.1:8000/docs>.

### 2. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL Vite prints, usually <http://localhost:5173>. During development Vite forwards `/api` requests to the local API at port 8000.

To create a production frontend build:

```powershell
cd frontend
npm run build
```

The generated static files are written to `frontend/dist/`.

## API routes

- `GET /api/health` — API health status
- `GET /api/filters` — available years and states/UTs
- `GET /api/summary` — impact totals
- `GET /api/charts` — chart series and correlation data
- `GET /api/records` — filtered and paginated records
- `GET /api/records/export` — filtered records as CSV
- `POST /api/upload` — validate and load a CSV for the running API process

Summary, chart, record, and export endpoints accept optional `year`, `state`, and `search` query parameters. The records endpoint also accepts pagination and sort parameters. CSV uploads are validated and held in memory for the current API process; they do not overwrite the repository's CSV files and are cleared when the API restarts.

## Data fields and interpretation

The dataset reports measures such as area affected (million hectares), population affected (millions), crop/house/public utility damage (Rs. crore), houses damaged, cattle lost, and human lives lost. Values are historical reports and should be interpreted using the units shown in the dashboard. They are not forecasts.

## Configuration

The FastAPI backend reads `data/CLEAN_FLOOD_DATA_CLEANED.csv` by default. Set `FLOOD_DATA_PATH` to use a different CSV file. For a separately hosted API, set `CORS_ORIGINS` to the frontend's allowed origin(s). For a separately hosted frontend, set `VITE_API_BASE_URL` to the API URL ending in `/api` before building the frontend. Do not put secrets in `VITE_` variables; those values are included in browser code.

