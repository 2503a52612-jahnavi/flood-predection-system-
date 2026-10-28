"""Clean the source flood CSV and write the dashboard-ready dataset.

Run this file from any directory with:
    python datacleaning.py

The source and output paths are based on this script's folder, so no
machine-specific path needs to be edited.
"""

from pathlib import Path

import pandas as pd


SCRIPT_FOLDER = Path(__file__).resolve().parent
SOURCE_FILE = SCRIPT_FOLDER / "RS_Session_250_AU86_Annexure-II.csv"
OUTPUT_FILE = SCRIPT_FOLDER / "CLEAN_FLOOD_DATA_CLEANED.csv"

STATE_COLUMN = "Name of State/UT"
YEAR_COLUMN = "Year"
SUMMARY_LABEL = "Total"


def clean_flood_data() -> None:
    """Clean the source file without discarding valid state-year records."""
    if not SOURCE_FILE.is_file():
        raise FileNotFoundError(f"Source CSV was not found: {SOURCE_FILE}")

    # Read as text first so pandas does not guess that labels such as "NA"
    # mean zero or silently convert a whole column to an unexpected type.
    data = pd.read_csv(SOURCE_FILE, dtype="string", keep_default_na=False)
    rows_read = len(data)

    # Trim header whitespace but otherwise keep every source column and its
    # original order. The current source headers are already trimmed.
    original_columns = list(data.columns)
    data.columns = [column.strip() for column in data.columns]
    whitespace_fixed = sum(
        old != new for old, new in zip(original_columns, data.columns)
    )
    if len(set(data.columns)) != len(data.columns):
        raise ValueError("Trimming column names created duplicate column names.")

    if STATE_COLUMN not in data.columns or YEAR_COLUMN not in data.columns:
        raise ValueError(
            f"The source CSV must contain '{YEAR_COLUMN}' and '{STATE_COLUMN}'."
        )

    # Trim values in all columns. State names are text; every other column in
    # this source dataset (including Year and Sl.No) contains numeric values.
    for column in data.columns:
        original_values = data[column]
        trimmed_values = original_values.str.strip()
        whitespace_fixed += int(original_values.ne(trimmed_values).sum())
        data[column] = trimmed_values

    state_names = data[STATE_COLUMN]
    blank_states = state_names.eq("")
    if blank_states.any():
        raise ValueError(
            f"Found {int(blank_states.sum())} row(s) with a blank "
            f"'{STATE_COLUMN}'. No rows were removed."
        )

    # "Total" rows are annual summaries, not state-year records. Keeping them
    # alongside state rows would double-count the annual impact in dashboards.
    is_annual_total = state_names.str.casefold().eq(SUMMARY_LABEL.casefold())
    annual_totals_removed = int(is_annual_total.sum())
    data = data.loc[~is_annual_total].copy()

    # Remove only exact duplicate records. Sl.No is a yearly serial number,
    # so it is not unique across years and is not used as a duplicate key.
    duplicate_rows_removed = int(data.duplicated().sum())
    data = data.drop_duplicates().copy()

    # The source uses "Nil" to indicate zero impact; the existing cleaned file
    # also represents these values as zero. Blank and "NA" values instead mean
    # unavailable, so keep them as missing rather than inventing a zero.
    numeric_columns = [column for column in data.columns if column != STATE_COLUMN]
    missing_markers = {"", "na", "n/a"}
    nil_values_fixed = 0
    missing_values_preserved = 0
    numeric_values_converted = 0

    for column in numeric_columns:
        values = data[column].str.strip()
        lowered = values.str.casefold()
        is_nil = lowered.eq("nil")
        is_missing = lowered.isin(missing_markers)

        nil_values_fixed += int(is_nil.sum())
        missing_values_preserved += int(is_missing.sum())

        # Convert only documented missing markers before numeric parsing.
        values = values.mask(is_nil, "0").mask(is_missing, pd.NA)
        converted = pd.to_numeric(values, errors="coerce")

        # Unexpected text is an error, not a reason to silently lose a value
        # or drop a record.
        invalid = values.notna() & converted.isna()
        if invalid.any():
            examples = values.loc[invalid].head(5).tolist()
            raise ValueError(
                f"Column '{column}' contains unexpected non-numeric value(s): "
                f"{examples}. No output was written."
            )

        numeric_values_converted += int(converted.notna().sum())
        if column == YEAR_COLUMN:
            if converted.isna().any():
                raise ValueError(
                    f"'{YEAR_COLUMN}' contains missing values. No output was written."
                )
            if converted.mod(1).ne(0).any():
                raise ValueError(
                    f"'{YEAR_COLUMN}' must contain whole years. No output was written."
                )
            data[column] = converted.astype("int64")
        else:
            data[column] = converted

    # Write only after validation and cleaning have succeeded, preserving all
    # source columns in their original order.
    data.to_csv(OUTPUT_FILE, index=False)

    rows_written = len(data)
    rows_removed = rows_read - rows_written
    print("Flood dataset cleaning complete.")
    print(f"Rows read: {rows_read}")
    print(f"Rows written: {rows_written}")
    print(f"Rows removed: {rows_removed}")
    print(f"  Annual 'Total' summary rows excluded: {annual_totals_removed}")
    print(f"  Exact duplicate state-year rows removed: {duplicate_rows_removed}")
    print("Values fixed or preserved:")
    print(f"  Whitespace-padded headers/cells trimmed: {whitespace_fixed}")
    print(f"  'Nil' values converted to numeric zero: {nil_values_fixed}")
    print(f"  Blank/'NA' numeric values preserved as missing: {missing_values_preserved}")
    print(f"  Numeric cells converted from text: {numeric_values_converted}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    clean_flood_data()
