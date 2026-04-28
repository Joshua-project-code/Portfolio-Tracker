from __future__ import annotations

import argparse
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


if __name__ == "__main__":
    main()
