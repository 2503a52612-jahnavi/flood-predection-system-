import io
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response


YEAR_COLUMN = "Year"
STATE_COLUMN = "Name of State/UT"
METRICS = {
    "area": "Area Affected (Mha)",
    "population": "Population Affected (Million)",
    "crop_damage": "Damages to Crops - Value (Rs. Crore)",
    "house_damage": "Damage to Houses - Value (Rs. Crore)",
    "houses_damaged": "Damage to Houses - Nos.",
    "cattle_lost": "Cattle Lost Nos.",
    "lives_lost": "Human Lives Lost Nos.",
    "public_damage": "Damage to Public Utilities (Rs. Crore)",
    "total_damage": "Total Damages Crops,Houses & Public Utilities (Rs. Crore)",
}
REQUIRED_COLUMNS = {YEAR_COLUMN, STATE_COLUMN, *METRICS.values()}
NUMERIC_COLUMNS = {YEAR_COLUMN, *METRICS.values()}
DISPLAY_COLUMNS = [
    "Sl.No",
    YEAR_COLUMN,
    STATE_COLUMN,
    "Area Affected (Mha)",
    "Population Affected (Million)",
    "Damages to Crops - Area (Mha)",
    "Damages to Crops - Value (Rs. Crore)",
    "Damage to Houses - Nos.",
    "Damage to Houses - Value (Rs. Crore)",
    "Cattle Lost Nos.",
    "Human Lives Lost Nos.",
    "Damage to Public Utilities (Rs. Crore)",
    "Total Damages Crops,Houses & Public Utilities (Rs. Crore)",
]
CORRELATION_METRICS = [
    ("Area affected (Mha)", METRICS["area"]),
    ("Population affected (million)", METRICS["population"]),
    ("Crop damage (Rs. crore)", METRICS["crop_damage"]),
    ("House damage (Rs. crore)", METRICS["house_damage"]),
    ("Lives lost", METRICS["lives_lost"]),
    ("Total damage (Rs. crore)", METRICS["total_damage"]),
]
DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "CLEAN_FLOOD_DATA_CLEANED.csv"
)
DATA_PATH = Path(os.getenv("FLOOD_DATA_PATH", str(DEFAULT_DATA_PATH))).expanduser()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

uploaded_data: pd.DataFrame | None = None

app = FastAPI(
    title="Floodcast API",
    description="Historical reported flood impacts for Indian States and UTs.",
    version="1.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate_data(data: pd.DataFrame) -> pd.DataFrame:
    missing_columns = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing_columns:
        raise ValueError(
            "CSV is missing required columns: " + ", ".join(missing_columns)
        )
    if data.empty:
        raise ValueError("CSV contains no records.")

    clean = data.copy()
    clean[STATE_COLUMN] = clean[STATE_COLUMN].astype("string").str.strip()
    if clean[STATE_COLUMN].isna().any() or clean[STATE_COLUMN].eq("").any():
        raise ValueError(f"'{STATE_COLUMN}' contains blank values.")

    for column in NUMERIC_COLUMNS:
        original = clean[column]
        parsed = pd.to_numeric(original, errors="coerce")
        malformed = original.notna() & original.astype(str).str.strip().ne("") & parsed.isna()
        if malformed.any():
            raise ValueError(
                f"'{column}' contains {int(malformed.sum())} non-numeric value(s)."
            )
        non_finite = parsed.notna() & ~np.isfinite(parsed)
        if non_finite.any():
            raise ValueError(f"'{column}' contains non-finite numeric value(s).")
        if column == YEAR_COLUMN and parsed.isna().any():
            raise ValueError(f"'{YEAR_COLUMN}' cannot be blank.")
        clean[column] = parsed.fillna(0)

    years = clean[YEAR_COLUMN]
    if ((years % 1) != 0).any() or years.lt(1900).any() or years.gt(2100).any():
        raise ValueError("'Year' must contain whole years between 1900 and 2100.")
    clean[YEAR_COLUMN] = years.astype(int)
    return clean


def get_data() -> pd.DataFrame:
    if uploaded_data is not None:
        return uploaded_data.copy()
    if not DATA_PATH.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                f"Flood dataset not found at {DATA_PATH}. Set FLOOD_DATA_PATH "
                "or place CLEAN_FLOOD_DATA_CLEANED.csv in the data directory."
            ),
        )
    try:
        return validate_data(pd.read_csv(DATA_PATH))
    except (OSError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        raise HTTPException(
            status_code=500, detail=f"Could not load flood dataset: {error}"
        ) from error


def filtered_data(
    year: int | None, state: str | None, search: str | None
) -> pd.DataFrame:
    data = get_data()
    if year is not None:
        if year not in set(data[YEAR_COLUMN].unique()):
            raise HTTPException(
                status_code=422,
                detail=f"Year {year} is not available in the active dataset.",
            )
        data = data[data[YEAR_COLUMN] == year]
    if state:
        if state not in set(data[STATE_COLUMN].unique()):
            raise HTTPException(
                status_code=422,
                detail=f"State/UT '{state}' is not available in the active dataset.",
            )
        data = data[data[STATE_COLUMN] == state]
    if search and search.strip():
        data = data[
            data[STATE_COLUMN].str.contains(search.strip(), case=False, regex=False)
        ]
    return data.copy()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/filters")
def get_filters() -> dict[str, Any]:
    data = get_data()
    return {
        "years": sorted(int(year) for year in data[YEAR_COLUMN].unique()),
        "states": sorted(str(state) for state in data[STATE_COLUMN].unique()),
        "records": int(len(data)),
        "source": "uploaded CSV" if uploaded_data is not None else DATA_PATH.name,
    }


@app.get("/api/summary")
def get_summary(
    year: int | None = Query(default=None, ge=1900, le=2100),
    state: str | None = Query(default=None, min_length=1, max_length=100),
    search: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    data = filtered_data(year, state, search)
    return {
        "population_affected_million": float(data[METRICS["population"]].sum()),
        "lives_lost": int(data[METRICS["lives_lost"]].sum()),
        "area_affected_mha": float(data[METRICS["area"]].sum()),
        "total_damage_crore": float(data[METRICS["total_damage"]].sum()),
        "records": int(len(data)),
        "states": int(data[STATE_COLUMN].nunique()),
    }


@app.get("/api/charts")
def get_charts(
    year: int | None = Query(default=None, ge=1900, le=2100),
    state: str | None = Query(default=None, min_length=1, max_length=100),
    search: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    data = filtered_data(year, state, search)

    lives = (
        data.groupby(STATE_COLUMN, as_index=False)[METRICS["lives_lost"]]
        .sum()
        .sort_values(METRICS["lives_lost"], ascending=False)
    )
    lives_top = lives.head(10)
    lives_chart = [
        {"name": str(row[STATE_COLUMN]), "value": int(row[METRICS["lives_lost"]])}
        for _, row in lives_top.iterrows()
    ]
    others = int(lives.iloc[10:][METRICS["lives_lost"]].sum())
    if others:
        lives_chart.append({"name": "Others", "value": others})

    area_values = data[METRICS["area"]].to_numpy(dtype=float)
    counts, edges = np.histogram(area_values, bins=20)
    area_distribution = [
        {
            "range": f"{edges[index]:.3g}–{edges[index + 1]:.3g}",
            "count": int(count),
            "lower": float(edges[index]),
            "upper": float(edges[index + 1]),
        }
        for index, count in enumerate(counts)
    ]

    population_by_year = (
        data.groupby(YEAR_COLUMN, as_index=False)[METRICS["population"]]
        .sum()
        .sort_values(YEAR_COLUMN)
    )
    crop_damage = (
        data.groupby(STATE_COLUMN, as_index=False)[METRICS["crop_damage"]]
        .sum()
        .sort_values(METRICS["crop_damage"], ascending=False)
        .head(10)
        .sort_values(METRICS["crop_damage"])
    )
    scatter = [
        {
            "state": str(row[STATE_COLUMN]),
            "year": int(row[YEAR_COLUMN]),
            "house_damage": float(row[METRICS["house_damage"]]),
            "population": float(row[METRICS["population"]]),
        }
        for _, row in data.iterrows()
    ]

    correlation_data = data[[column for _, column in CORRELATION_METRICS]].corr()
    correlation_labels = [label for label, _ in CORRELATION_METRICS]
    correlations = [
        [
            None if pd.isna(value) else round(float(value), 4)
            for value in correlation_data.loc[
                [column for _, column in CORRELATION_METRICS][row_index]
            ]
        ]
        for row_index in range(len(CORRELATION_METRICS))
    ]

    return {
        "lives_lost_by_state": lives_chart,
        "area_distribution": area_distribution,
        "population_by_year": [
            {
                "year": int(row[YEAR_COLUMN]),
                "population": float(row[METRICS["population"]]),
            }
            for _, row in population_by_year.iterrows()
        ],
        "crop_damage_by_state": [
            {
                "state": str(row[STATE_COLUMN]),
                "crop_damage": float(row[METRICS["crop_damage"]]),
            }
            for _, row in crop_damage.iterrows()
        ],
        "house_damage_vs_population": scatter,
        "correlation_labels": correlation_labels,
        "correlations": correlations,
    }


@app.get("/api/records")
def get_records(
    year: int | None = Query(default=None, ge=1900, le=2100),
    state: str | None = Query(default=None, min_length=1, max_length=100),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default=YEAR_COLUMN),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    data = filtered_data(year, state, search)
    sortable = set(DISPLAY_COLUMNS) - {"Sl.No"}
    if sort_by not in sortable:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported sort_by column. Choose from: {', '.join(sorted(sortable))}.",
        )
    data = data.sort_values(
        sort_by, ascending=sort_order == "asc", kind="stable", na_position="last"
    )
    total = len(data)
    start = (page - 1) * page_size
    columns = [column for column in DISPLAY_COLUMNS if column in data.columns]
    records = data.iloc[start : start + page_size][columns].where(
        pd.notna(data.iloc[start : start + page_size][columns]), None
    )
    return {
        "records": records.to_dict(orient="records"),
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


@app.get("/api/records/export")
def export_records(
    year: int | None = Query(default=None, ge=1900, le=2100),
    state: str | None = Query(default=None, min_length=1, max_length=100),
    search: str | None = Query(default=None, max_length=100),
) -> Response:
    data = filtered_data(year, state, search)
    csv_content = data.to_csv(index=False)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="flood-impact-records.csv"'},
    )


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)) -> dict[str, Any]:
    global uploaded_data
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Choose a .csv file to upload.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="CSV upload exceeds the 10 MB size limit."
        )
    try:
        incoming = pd.read_csv(io.BytesIO(content))
        clean = validate_data(incoming)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if clean.empty:
        raise HTTPException(status_code=422, detail="CSV contains no records.")

    uploaded_data = clean
    return {
        "message": "CSV validated and loaded for this server session.",
        "records": int(len(clean)),
        "years": sorted(int(value) for value in clean[YEAR_COLUMN].unique()),
        "states": int(clean[STATE_COLUMN].nunique()),
    }
