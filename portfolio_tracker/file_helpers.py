# This module centralizes filesystem and source-file discovery helpers used by
# the broker parsers. It contains clean_column_name(), find_sheet_name(),
# find_workbooks(), find_csv_files(), ensure_folder_exists(), and
# get_broker_name() for normalizing columns, locating input files, creating
# output folders, and inferring broker names from paths.

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .constants import CSV_EXTENSIONS, EXCEL_EXTENSIONS


def clean_column_name(column: str) -> str:
    """Normalize a source spreadsheet column name into snake_case."""
    return str(column).strip().lower().replace("/", "").replace(" ", "_")


def find_sheet_name(workbook_path: Path, prefix: str) -> str:
    """Return the first Excel sheet name that starts with the given prefix."""
    sheet_names = pd.ExcelFile(workbook_path).sheet_names
    matches = [name for name in sheet_names if name.lower().startswith(prefix.lower())]
    if not matches:
        raise ValueError(
            f"No sheet starting with {prefix!r} found. Available sheets: {sheet_names}"
        )
    return matches[0]


def find_workbooks(input_path: Path) -> list[Path]:
    """Return Excel workbook paths from a file or folder input."""
    if input_path.is_file():
        if input_path.suffix.lower() not in EXCEL_EXTENSIONS:
            raise ValueError(f"Input file is not an Excel workbook: {input_path}")
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    workbooks = sorted(
        path
        for path in input_path.iterdir()
        if path.is_file()
        and path.suffix.lower() in EXCEL_EXTENSIONS
        # Ignore temporary lock files created by Excel while a workbook is open.
        and not path.name.startswith("~$")
    )
    if not workbooks:
        raise FileNotFoundError(f"No Excel workbooks found in folder: {input_path}")

    return workbooks


def find_csv_files(input_path: Path) -> list[Path]:
    """Return CSV file paths from a file or folder input."""
    if input_path.is_file():
        if input_path.suffix.lower() not in CSV_EXTENSIONS:
            raise ValueError(f"Input file is not a CSV file: {input_path}")
        return [input_path]

    if not input_path.is_dir():
        return []

    return sorted(
        path
        for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower() in CSV_EXTENSIONS
    )


def ensure_folder_exists(folder_path: Path) -> None:
    """Create a folder when it does not already exist."""
    if folder_path.is_dir():
        return

    folder_path.mkdir(parents=True, exist_ok=True)
    print(f"Created missing folder: {folder_path}")


def get_broker_name(file_path: Path) -> str:
    """Infer the broker name from the containing folder path."""
    for parent in [file_path.parent, *file_path.parents]:
        if parent.name.lower() == "poems":
            return "poems"
        if parent.name.lower() == "interactive brokers":
            return "interactive brokers"
    return file_path.parent.name.lower()
