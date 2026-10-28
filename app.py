from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_FILE = Path(__file__).parent / "CLEAN_FLOOD_DATA_CLEANED.csv"

YEAR_COLUMN = "Year"
STATE_COLUMN = "Name of State/UT"

METRICS = {
    "Area affected (Mha)": "Area Affected (Mha)",
    "Population affected (million)": "Population Affected (Million)",
    "Crop damage (Rs. crore)": "Damages to Crops - Value (Rs. Crore)",
    "House damage (Rs. crore)": "Damage to Houses - Value (Rs. Crore)",
    "Public utility damage (Rs. crore)": "Damage to Public Utilities (Rs. Crore)",
    "Human lives lost": "Human Lives Lost Nos.",
    "Cattle lost": "Cattle Lost Nos.",
    "Total damage (Rs. crore)": (
        "Total Damages Crops,Houses & Public Utilities (Rs. Crore)"
    ),
}

REQUIRED_COLUMNS = {
    YEAR_COLUMN,
    STATE_COLUMN,
    *METRICS.values(),
    "Damage to Houses - Nos.",
}


@st.cache_data
def load_flood_data() -> pd.DataFrame:
    if not DATA_FILE.is_file():
        raise FileNotFoundError(
            f"Could not find {DATA_FILE.name}. Place it beside app.py and try again."
        )

    data = pd.read_csv(DATA_FILE)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing_columns:
        raise ValueError(
            "The dataset is missing required columns: " + ", ".join(missing_columns)
        )
    if data.empty:
        raise ValueError("The flood dataset contains no records.")

    data = data.copy()
    data[YEAR_COLUMN] = pd.to_numeric(data[YEAR_COLUMN], errors="raise").astype(int)
    for column in METRICS.values():
        data[column] = pd.to_numeric(data[column], errors="raise")
    data["Damage to Houses - Nos."] = pd.to_numeric(
        data["Damage to Houses - Nos."], errors="raise"
    )
    return data


def format_total(value: float, suffix: str = "") -> str:
    return f"{value:,.2f}{suffix}"


st.set_page_config(
    page_title="Flood impact dashboard",
    page_icon=":material/water_drop:",
    layout="wide",
)

st.title("Flood impact dashboard")
st.caption(
    "Explore reported flood impacts across Indian States and Union Territories."
)

try:
    flood_data = load_flood_data()
except (FileNotFoundError, ValueError) as error:
    st.error(str(error))
    st.stop()

available_years = sorted(flood_data[YEAR_COLUMN].unique().tolist())
available_states = sorted(flood_data[STATE_COLUMN].dropna().unique().tolist())

with st.sidebar:
    st.header("Dashboard filters")
    selected_years = st.multiselect(
        "Years",
        options=available_years,
        default=available_years,
    )
    selected_states = st.multiselect(
        "States and Union Territories",
        options=available_states,
        default=available_states,
    )
    selected_metric_label = st.selectbox(
        "Metric for state comparison",
        options=list(METRICS),
        index=0,
    )
    st.caption(f"Source: {DATA_FILE.name}")

if not selected_years or not selected_states:
    st.info("Select at least one year and one State/UT to view the dashboard.")
    st.stop()

filtered_data = flood_data[
    flood_data[YEAR_COLUMN].isin(selected_years)
    & flood_data[STATE_COLUMN].isin(selected_states)
].copy()

population_total = filtered_data[METRICS["Population affected (million)"]].sum()
area_total = filtered_data[METRICS["Area affected (Mha)"]].sum()
lives_total = filtered_data[METRICS["Human lives lost"]].sum()
damage_total = filtered_data[METRICS["Total damage (Rs. crore)"]].sum()

with st.container(horizontal=True):
    st.metric(
        "Population affected",
        format_total(population_total, " M"),
        border=True,
    )
    st.metric(
        "Area affected",
        format_total(area_total, " Mha"),
        border=True,
    )
    st.metric("Human lives lost", f"{lives_total:,.0f}", border=True)
    st.metric(
        "Reported total damage",
        format_total(damage_total, " crore"),
        border=True,
    )

st.caption(
    f"Showing {len(filtered_data):,} state-year records across "
    f"{filtered_data[STATE_COLUMN].nunique()} selected States/UTs."
)

metric_column = METRICS[selected_metric_label]
yearly_metric = (
    filtered_data.groupby(YEAR_COLUMN, as_index=False)[metric_column]
    .sum()
    .sort_values(YEAR_COLUMN)
)
state_metric = (
    filtered_data.groupby(STATE_COLUMN, as_index=False)[metric_column]
    .sum()
    .sort_values(metric_column, ascending=False)
    .head(10)
)

trend_column, state_column = st.columns(2)
with trend_column:
    with st.container(border=True):
        st.subheader(f"{selected_metric_label} by year")
        trend_chart = px.line(
            yearly_metric,
            x=YEAR_COLUMN,
            y=metric_column,
            markers=True,
            labels={YEAR_COLUMN: "Year", metric_column: selected_metric_label},
        )
        trend_chart.update_layout(
            margin=dict(l=12, r=12, t=16, b=12),
            hovermode="x unified",
        )
        st.plotly_chart(trend_chart, width="stretch")

with state_column:
    with st.container(border=True):
        st.subheader(f"Top States/UTs: {selected_metric_label}")
        state_chart = px.bar(
            state_metric.sort_values(metric_column, ascending=True),
            x=metric_column,
            y=STATE_COLUMN,
            orientation="h",
            labels={
                metric_column: selected_metric_label,
                STATE_COLUMN: "State/UT",
            },
            color_discrete_sequence=["#168C91"],
        )
        state_chart.update_layout(
            margin=dict(l=12, r=12, t=16, b=12),
            yaxis_title=None,
            xaxis_title=selected_metric_label,
        )
        st.plotly_chart(state_chart, width="stretch")

damage_columns = {
    "Crop damage": METRICS["Crop damage (Rs. crore)"],
    "House damage": METRICS["House damage (Rs. crore)"],
    "Public utility damage": METRICS["Public utility damage (Rs. crore)"],
}
damage_by_year = (
    filtered_data.groupby(YEAR_COLUMN, as_index=False)[list(damage_columns.values())]
    .sum()
    .rename(columns={value: label for label, value in damage_columns.items()})
    .melt(id_vars=YEAR_COLUMN, var_name="Damage category", value_name="Rs. crore")
)

scatter_column, damage_column = st.columns(2)
with damage_column:
    with st.container(border=True):
        st.subheader("Reported damage by year")
        damage_chart = px.bar(
            damage_by_year,
            x=YEAR_COLUMN,
            y="Rs. crore",
            color="Damage category",
            barmode="stack",
            labels={YEAR_COLUMN: "Year", "Rs. crore": "Rs. crore"},
            color_discrete_sequence=["#168C91", "#F2A65A", "#6675C9"],
        )
        damage_chart.update_layout(margin=dict(l=12, r=12, t=16, b=12))
        st.plotly_chart(damage_chart, width="stretch")

with scatter_column:
    with st.container(border=True):
        st.subheader("Compare flood impacts")
        axis_options = list(METRICS)
        x_choice, y_choice = st.columns(2)
        with x_choice:
            x_label = st.selectbox(
                "Horizontal axis",
                options=axis_options,
                index=1,
            )
        with y_choice:
            y_label = st.selectbox(
                "Vertical axis",
                options=axis_options,
                index=5,
            )

        scatter_chart = px.scatter(
            filtered_data,
            x=METRICS[x_label],
            y=METRICS[y_label],
            color=YEAR_COLUMN,
            hover_name=STATE_COLUMN,
            hover_data={YEAR_COLUMN: True},
            labels={
                METRICS[x_label]: x_label,
                METRICS[y_label]: y_label,
                YEAR_COLUMN: "Year",
            },
            color_continuous_scale="Teal",
        )
        scatter_chart.update_layout(margin=dict(l=12, r=12, t=16, b=12))
        st.plotly_chart(scatter_chart, width="stretch")

with st.container(border=True):
    st.subheader("State-level records")
    search_text = st.text_input(
        "Search States/UTs",
        placeholder="Type a State or Union Territory name",
    )

    display_columns = [
        YEAR_COLUMN,
        STATE_COLUMN,
        METRICS["Area affected (Mha)"],
        METRICS["Population affected (million)"],
        "Damage to Houses - Nos.",
        METRICS["Human lives lost"],
        METRICS["Total damage (Rs. crore)"],
    ]
    display_data = filtered_data[display_columns].rename(
        columns={
            YEAR_COLUMN: "Year",
            STATE_COLUMN: "State/UT",
            METRICS["Area affected (Mha)"]: "Area affected (Mha)",
            METRICS["Population affected (million)"]: "Population affected (million)",
            "Damage to Houses - Nos.": "Houses damaged",
            METRICS["Human lives lost"]: "Human lives lost",
            METRICS["Total damage (Rs. crore)"]: "Total damage (Rs. crore)",
        }
    )
    if search_text.strip():
        display_data = display_data[
            display_data["State/UT"].str.contains(
                search_text.strip(), case=False, regex=False, na=False
            )
        ]

    st.dataframe(display_data, hide_index=True)
    st.download_button(
        "Download displayed records",
        data=display_data.to_csv(index=False).encode("utf-8"),
        file_name="flood_impact_records.csv",
        mime="text/csv",
        icon=":material/download:",
    )
