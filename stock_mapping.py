# This module loads and applies stock classification metadata used by the chart
# outputs. It contains load_stock_mapping() to read sector/geography mappings
# from CSV, normalize_stock_name() to make stock names comparable across broker
# exports, and enrich_positions_with_mapping() to add mapping columns to the
# parsed investment positions DataFrame.

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_stock_mapping(mapping_path: Path) -> pd.DataFrame:
    """Load stock sector and geography mapping from CSV."""
    if not mapping_path.is_file():
        print(f"Stock mapping file not found. Skipping pie charts: {mapping_path}")
        return pd.DataFrame(columns=["stock_name_key", "sector", "geography"])

    mapping = pd.read_csv(mapping_path)
    required_columns = {"stock_name", "sector", "geography"}
    missing_columns = required_columns - set(mapping.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Stock mapping CSV is missing required column(s): {missing}")

    mapping = mapping[["stock_name", "sector", "geography"]].copy()
    mapping["stock_name_key"] = normalize_stock_name(mapping["stock_name"])
    mapping["sector"] = mapping["sector"].fillna("Unmapped").astype(str).str.strip()
    mapping["geography"] = mapping["geography"].fillna("Unmapped").astype(str).str.strip()

    return mapping.drop_duplicates("stock_name_key")


def normalize_stock_name(stock_names: pd.Series) -> pd.Series:
    """Normalize stock names for mapping lookups."""
    return stock_names.fillna("").astype(str).str.strip().str.upper()


def enrich_positions_with_mapping(
    positions_df: pd.DataFrame, mapping_df: pd.DataFrame
) -> pd.DataFrame:
    """Add sector and geography columns to positions using the stock mapping."""
    if positions_df.empty:
        return positions_df.assign(
            sector=pd.Series(dtype="object"),
            geography=pd.Series(dtype="object"),
        )

    positions = positions_df.copy()
    positions["stock_name_key"] = normalize_stock_name(positions["stock_name"])
    positions = positions.merge(
        mapping_df[["stock_name_key", "sector", "geography"]],
        on="stock_name_key",
        how="left",
    )
    positions["sector"] = positions["sector"].fillna("Unmapped")
    positions["geography"] = positions["geography"].fillna("Unmapped")
    positions = positions.drop(columns=["stock_name_key"])

    unmapped = positions.loc[
        (positions["sector"] == "Unmapped") | (positions["geography"] == "Unmapped"),
        "stock_name",
    ].drop_duplicates()
    if not unmapped.empty:
        print("Unmapped stock name(s) found. Update stock_mapping.csv if needed:")
        for stock_name in unmapped:
            print(f"- {stock_name}")

    return positions
