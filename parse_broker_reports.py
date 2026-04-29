# This module is the command-line entry point for the broker report parser. It
# contains wait_for_broker_files() for locating or prompting for source files,
# build_dataframes() for combining POEMS and Interactive Brokers data, main()
# and run_parser() for the end-to-end workflow, and the user-friendly error
# helpers print_user_friendly_error() and get_user_friendly_error_message().

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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


def main() -> None:
    """Run the parser and show clear errors for common user-fixable problems."""
    try:
        run_parser()
    except KeyboardInterrupt:
        print("\nParser stopped by user.")
        sys.exit(1)
    except Exception as error:
        print_user_friendly_error(error)
        sys.exit(1)


def run_parser() -> None:
    """Parse command-line arguments, build dataframes, and print report previews."""
    parser = argparse.ArgumentParser(
        description="Parse broker transaction details and investment positions."
    )
    parser.add_argument(
        "root_path",
        nargs="?",
        type=Path,
        default=DEFAULT_BROKER_ROOT_PATH,
        help=(
            "Path to the folder containing POEMS and Interactive Brokers folders. "
            "Defaults to the parent folder of this project."
        ),
    )
    args = parser.parse_args()

    poems_path = args.root_path / "POEMS"
    interactive_brokers_path = args.root_path / "Interactive Brokers"
    workbooks = wait_for_broker_files(
        "POEMS",
        poems_path,
        "POEMS Excel workbook(s)",
        find_workbooks,
    )
    csv_files = wait_for_broker_files(
        "Interactive Brokers",
        interactive_brokers_path,
        "Interactive Brokers CSV file(s)",
        find_csv_files,
    )

    transactions_df, positions_df = build_dataframes(workbooks, interactive_brokers_path)

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


def print_user_friendly_error(error: Exception) -> None:
    """Print a plain-language error message instead of a Python traceback."""
    print("\nThe parser could not complete.")
    print(get_user_friendly_error_message(error))


def get_user_friendly_error_message(error: Exception) -> str:
    """Translate common exceptions into messages a non-technical user can act on."""
    error_text = str(error)

    if isinstance(error, PermissionError):
        return (
            "A file or folder could not be opened or saved because permission was denied.\n"
            "Please close any open CSV, Excel, or chart files in the Output, POEMS, "
            "or Interactive Brokers folders, then run the parser again."
        )

    if isinstance(error, FileNotFoundError):
        return (
            "A required file or folder could not be found.\n"
            f"Details: {error_text}\n"
            "Please check that the POEMS, Interactive Brokers, Output, and "
            "stock_mapping.csv locations are correct."
        )

    if isinstance(error, ModuleNotFoundError):
        missing_module = getattr(error, "name", None) or error_text
        return (
            f"A required Python package is not installed: {missing_module}\n"
            "Please install the project dependencies with:\n"
            "python -m pip install pandas openpyxl matplotlib"
        )

    if error.__class__.__name__ in {"BadZipFile", "InvalidFileException"}:
        return (
            "One of the Excel files could not be opened as a valid workbook.\n"
            "Please re-download or re-export the POEMS file, then try again."
        )

    if error.__class__.__name__ in {"ParserError", "EmptyDataError"}:
        return (
            "One of the CSV files could not be read correctly.\n"
            "Please check that the Interactive Brokers file is a valid CSV export "
            "and is not empty."
        )

    if isinstance(error, KeyError):
        return (
            "A required column was missing from one of the input files.\n"
            f"Missing item: {error_text}\n"
            "Please check that the broker export format has not changed and that "
            "stock_mapping.csv has the columns stock_name, sector, and geography."
        )

    if isinstance(error, ValueError):
        return (
            f"{error_text}\n"
            "Please correct the file mentioned above, then run the parser again."
        )

    return (
        "An unexpected problem occurred while reading the broker files or saving outputs.\n"
        f"Details: {error_text}\n"
        "Please check that the files are not open in another program and that the "
        "input files are in the expected broker export format."
    )


if __name__ == "__main__":
    main()
