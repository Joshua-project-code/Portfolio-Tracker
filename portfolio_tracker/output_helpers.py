# This module contains helpers for writing parser outputs to disk. It provides
# save_dataframes_to_csv() to save the final transactions and positions tables
# with date-stamped filenames, and save_dataframe_to_csv() to write one
# DataFrame while printing whether the file was created or overwritten.

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .file_helpers import ensure_folder_exists


def save_dataframes_to_csv(
    transactions_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    output_path: Path,
    generated_on: str | None = None,
) -> None:
    """Save the final dataframes as dated CSV files in the output folder."""
    ensure_folder_exists(output_path)
    today = generated_on or date.today().isoformat()

    transactions_file = output_path / f"transactions_{today}.csv"
    positions_file = output_path / f"positions_{today}.csv"

    save_dataframe_to_csv(transactions_df, transactions_file, "transactions dataframe")
    save_dataframe_to_csv(positions_df, positions_file, "investment positions dataframe")


def save_dataframe_to_csv(
    dataframe: pd.DataFrame, output_file: Path, description: str
) -> None:
    """Save one dataframe, overwriting only an existing file with the same name."""
    action = "Overwriting existing" if output_file.exists() else "Creating new"
    dataframe.to_csv(output_file, index=False)
    print(f"{action} {description} file: {output_file}")
