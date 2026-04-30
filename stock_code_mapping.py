# This module builds and persists a stock-code-to-stock-name lookup from parsed
# broker data. It contains helpers to extract mappings from transactions and
# positions, merge them with the persisted mapping file, and preserve old stock
# names when a broker reports a changed name for the same immutable stock code.

from __future__ import annotations

from pathlib import Path

import pandas as pd

from file_helpers import ensure_folder_exists


STOCK_CODE_MAPPING_COLUMNS = ["stock_code", "stock_name", "old_stock_names"]


def normalize_mapping_value(value: object) -> object:
    """Normalize mapping values while preserving missing values as pandas NA."""
    if pd.isna(value):
        return pd.NA

    text = str(value).strip()
    if not text:
        return pd.NA

    return text


def append_unique_name(names: list[str], value: object) -> None:
    """Append a normalized stock name to a list when it is present and unique."""
    normalized = normalize_mapping_value(value)
    if pd.isna(normalized):
        return

    name = str(normalized)
    if name not in names:
        names.append(name)


def split_old_stock_names(value: object) -> list[str]:
    """Split persisted historical stock names into a normalized unique list."""
    if pd.isna(value):
        return []

    names: list[str] = []
    for name in str(value).split("|"):
        append_unique_name(names, name)
    return names


def extract_stock_code_name_pairs(*dataframes: pd.DataFrame) -> pd.DataFrame:
    """Extract stock-code/name pairs from parsed broker dataframes."""
    frames: list[pd.DataFrame] = []
    for dataframe in dataframes:
        if dataframe.empty or "stock_code" not in dataframe.columns:
            continue

        frame = dataframe.copy()
        if "stock_name" not in frame.columns:
            frame["stock_name"] = pd.NA

        frame = frame[["stock_code", "stock_name"]]
        frame["stock_code"] = frame["stock_code"].map(normalize_mapping_value)
        frame["stock_name"] = frame["stock_name"].map(normalize_mapping_value)
        frame = frame.dropna(subset=["stock_code"])
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=["stock_code", "stock_name"])

    return pd.concat(frames, ignore_index=True).drop_duplicates(ignore_index=True)


def build_stock_code_mapping(
    current_pairs: pd.DataFrame, existing_mapping: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Merge current code/name pairs with an existing persisted mapping."""
    names_by_code: dict[str, list[str]] = {}
    latest_name_by_code: dict[str, object] = {}

    if existing_mapping is not None and not existing_mapping.empty:
        for _, row in existing_mapping.iterrows():
            stock_code = normalize_mapping_value(row.get("stock_code"))
            if pd.isna(stock_code):
                continue

            code = str(stock_code)
            names_by_code.setdefault(code, [])
            append_unique_name(names_by_code[code], row.get("stock_name"))
            for old_name in split_old_stock_names(row.get("old_stock_names")):
                append_unique_name(names_by_code[code], old_name)

            stock_name = normalize_mapping_value(row.get("stock_name"))
            if not pd.isna(stock_name):
                latest_name_by_code[code] = str(stock_name)

    if not current_pairs.empty:
        for _, row in current_pairs.iterrows():
            stock_code = normalize_mapping_value(row.get("stock_code"))
            if pd.isna(stock_code):
                continue

            code = str(stock_code)
            names_by_code.setdefault(code, [])
            stock_name = normalize_mapping_value(row.get("stock_name"))
            append_unique_name(names_by_code[code], stock_name)
            if not pd.isna(stock_name):
                latest_name_by_code[code] = str(stock_name)

    records: list[dict[str, object]] = []
    for stock_code in sorted(names_by_code):
        latest_name = latest_name_by_code.get(stock_code, pd.NA)
        historical_names = [
            name for name in names_by_code[stock_code] if name != latest_name
        ]
        records.append(
            {
                "stock_code": stock_code,
                "stock_name": latest_name,
                "old_stock_names": "|".join(historical_names) or pd.NA,
            }
        )

    return pd.DataFrame(records, columns=STOCK_CODE_MAPPING_COLUMNS)


def load_existing_stock_code_mapping(mapping_path: Path) -> pd.DataFrame:
    """Load the persisted stock-code mapping file if it exists."""
    if not mapping_path.is_file():
        return pd.DataFrame(columns=STOCK_CODE_MAPPING_COLUMNS)

    mapping = pd.read_csv(mapping_path)
    for column in STOCK_CODE_MAPPING_COLUMNS:
        if column not in mapping.columns:
            mapping[column] = pd.NA

    return mapping[STOCK_CODE_MAPPING_COLUMNS]


def save_stock_code_mapping(
    transactions_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    mapping_path: Path,
) -> pd.DataFrame:
    """Persist the stock-code mapping and return the saved dataframe."""
    current_pairs = extract_stock_code_name_pairs(transactions_df, positions_df)
    existing_mapping = load_existing_stock_code_mapping(mapping_path)
    mapping = build_stock_code_mapping(current_pairs, existing_mapping)

    ensure_folder_exists(mapping_path.parent)
    mapping.to_csv(mapping_path, index=False)
    print(f"Saved stock code mapping file: {mapping_path}")

    return mapping
