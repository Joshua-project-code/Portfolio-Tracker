# This module runs the Portfolio Tracker report workflow for both the CLI and
# Flask web app. It contains broker file discovery, dataframe construction,
# console-preview printing, CSV/chart output generation, and JSON-friendly
# report serialization helpers.

from __future__ import annotations

import contextlib
import io
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from chart_helpers import (
    build_monthly_position_totals,
    build_monthly_transaction_totals,
    save_monthly_position_chart,
    save_monthly_transaction_chart,
    save_position_distribution_pie_chart,
)
from constants import (
    DEFAULT_BROKER_ROOT_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_STOCK_MAPPING_PATH,
)
from file_helpers import ensure_folder_exists, find_csv_files, find_workbooks
from interactive_brokers_parser import (
    parse_interactive_brokers_positions_folder,
    parse_interactive_brokers_transactions_folder,
)
from output_helpers import save_dataframes_to_csv
from poems_parser import parse_poems_workbooks
from stock_mapping import enrich_positions_with_mapping, load_stock_mapping
from validation import print_duplicate_records_message


def wait_for_broker_files(
    broker_name: str,
    folder_path: Path,
    file_description: str,
    find_files,
) -> list[Path]:
    """Prompt once when a broker folder has no files, then continue if still empty."""
    ensure_folder_exists(folder_path)
    try:
        files = find_files(folder_path)
    except FileNotFoundError:
        files = []
    if files:
        return files

    print(f"\nNo {file_description} found in the {broker_name} folder:")
    print(folder_path)
    input(f"Upload {file_description} into this folder, then press Enter to continue.")

    try:
        files = find_files(folder_path)
    except FileNotFoundError:
        files = []
    if not files:
        print(f"No {file_description} found. Continuing without {broker_name} data.")

    return files


def find_broker_files_for_report(
    broker_name: str,
    folder_path: Path,
    file_description: str,
    find_files,
) -> list[Path]:
    """Find broker files without waiting for terminal input."""
    ensure_folder_exists(folder_path)
    try:
        files = find_files(folder_path)
    except FileNotFoundError:
        files = []

    if not files:
        print(f"No {file_description} found in the {broker_name} folder:")
        print(folder_path)
        print(f"Continuing without {broker_name} data.")

    return files


def build_dataframes(
    workbooks: list[Path],
    interactive_brokers_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the combined transactions and positions dataframes from broker folders."""
    # POEMS provides both transactions and positions; IBKR provides both from CSV sections.
    poems_transactions_df, poems_positions_df = parse_poems_workbooks(workbooks)
    ib_transactions_df = parse_interactive_brokers_transactions_folder(
        interactive_brokers_path
    )
    ib_positions_df = parse_interactive_brokers_positions_folder(
        interactive_brokers_path
    )

    # Keep transaction history chronological and positions ranked by current size.
    transactions_df = pd.concat(
        [poems_transactions_df, ib_transactions_df],
        ignore_index=True,
    ).sort_values("transaction_date", ignore_index=True)
    positions_df = pd.concat(
        [poems_positions_df, ib_positions_df],
        ignore_index=True,
    ).sort_values("market_value", ascending=False, ignore_index=True)

    return transactions_df, positions_df


def print_report_preview(
    workbooks: list[Path],
    csv_files: list[Path],
    transactions_df: pd.DataFrame,
    positions_df: pd.DataFrame,
) -> None:
    """Print the same report preview used by the legacy console workflow."""
    print_duplicate_records_message("transactions_df", transactions_df)
    print_duplicate_records_message("positions_df", positions_df)

    print(f"Loaded {len(workbooks)} POEMS workbook(s):")
    for workbook_path in workbooks:
        print(f"- {workbook_path.name}")
    print(f"Loaded {len(csv_files)} Interactive Brokers CSV file(s).")
    for csv_file in csv_files:
        print(f"- {csv_file.name}")

    print("Transaction Details - top 20 rows")
    print(transactions_df.head(20).to_string(index=False))

    print("\nInvestment Positions - top 30 rows")
    print(positions_df.head(30).to_string(index=False))


def save_report_outputs(
    workbooks: list[Path],
    csv_files: list[Path],
    transactions_df: pd.DataFrame,
    positions_df: pd.DataFrame,
) -> None:
    """Save report CSV files and chart images to the configured output folder."""
    save_dataframes_to_csv(transactions_df, positions_df, DEFAULT_OUTPUT_PATH)
    monthly_totals_df = build_monthly_position_totals(workbooks, csv_files)
    save_monthly_position_chart(monthly_totals_df, DEFAULT_OUTPUT_PATH)
    monthly_transactions_df = build_monthly_transaction_totals(transactions_df)
    save_monthly_transaction_chart(monthly_transactions_df, DEFAULT_OUTPUT_PATH)
    stock_mapping_df = load_stock_mapping(DEFAULT_STOCK_MAPPING_PATH)
    mapped_positions_df = enrich_positions_with_mapping(positions_df, stock_mapping_df)
    save_position_distribution_pie_chart(
        mapped_positions_df,
        "sector",
        "Sector Distribution by Currency",
        "sector_distribution",
        DEFAULT_OUTPUT_PATH,
    )
    save_position_distribution_pie_chart(
        mapped_positions_df,
        "geography",
        "Geography Distribution by Currency",
        "geography_distribution",
        DEFAULT_OUTPUT_PATH,
    )


def dataframe_table(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Convert a full DataFrame into JSON-friendly table data."""
    table = dataframe.copy()
    table = table.astype(object).where(pd.notna(table), "")
    return {
        "columns": table.columns.tolist(),
        "rows": [
            {column: format_table_value(value) for column, value in row.items()}
            for row in table.to_dict("records")
        ],
        "total_rows": len(dataframe),
    }


def format_table_value(value: Any) -> Any:
    """Convert pandas and path objects into values Flask can serialize as JSON."""
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def get_generated_output_names(today: str) -> tuple[list[str], list[str]]:
    """Return generated chart and CSV names that currently exist on disk."""
    chart_names = [
        f"investment_positions_by_month_{today}.png",
        f"transactions_by_month_{today}.png",
        f"sector_distribution_{today}.png",
        f"geography_distribution_{today}.png",
    ]
    csv_names = [
        f"transactions_{today}.csv",
        f"positions_{today}.csv",
    ]

    existing_charts = [
        name for name in chart_names if (DEFAULT_OUTPUT_PATH / name).exists()
    ]
    existing_csvs = [name for name in csv_names if (DEFAULT_OUTPUT_PATH / name).exists()]

    return existing_charts, existing_csvs


def run_report(
    root_path: Path = DEFAULT_BROKER_ROOT_PATH,
    prompt_for_missing_files: bool = False,
) -> dict[str, Any]:
    """Run the full parser workflow and return data suitable for the web app."""
    poems_path = root_path / "POEMS"
    interactive_brokers_path = root_path / "Interactive Brokers"
    file_finder = (
        wait_for_broker_files
        if prompt_for_missing_files
        else find_broker_files_for_report
    )
    workbooks = file_finder(
        "POEMS",
        poems_path,
        "POEMS Excel workbook(s)",
        find_workbooks,
    )
    csv_files = file_finder(
        "Interactive Brokers",
        interactive_brokers_path,
        "Interactive Brokers CSV file(s)",
        find_csv_files,
    )

    transactions_df, positions_df = build_dataframes(workbooks, interactive_brokers_path)
    print_report_preview(workbooks, csv_files, transactions_df, positions_df)
    save_report_outputs(workbooks, csv_files, transactions_df, positions_df)

    today = date.today().isoformat()
    chart_names, csv_names = get_generated_output_names(today)

    return {
        "root_path": str(root_path),
        "output_path": str(DEFAULT_OUTPUT_PATH),
        "generated_on": today,
        "poems_files": [path.name for path in workbooks],
        "interactive_brokers_files": [path.name for path in csv_files],
        "transactions": dataframe_table(transactions_df),
        "positions": dataframe_table(positions_df),
        "charts": chart_names,
        "csv_files": csv_names,
    }


def run_report_with_console_output(
    root_path: Path = DEFAULT_BROKER_ROOT_PATH,
) -> dict[str, Any]:
    """Run the report and include the legacy console output as captured text."""
    output_buffer = io.StringIO()
    with contextlib.redirect_stdout(output_buffer):
        report = run_report(root_path=root_path, prompt_for_missing_files=False)
    report["console_output"] = output_buffer.getvalue()
    return report
