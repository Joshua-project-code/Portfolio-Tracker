from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

import pandas as pd

from constants import (
    DEFAULT_BROKER_ROOT_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_STOCK_MAPPING_PATH,
)
from file_helpers import find_csv_files, find_workbooks
from interactive_brokers_parser import (
    parse_interactive_brokers_positions,
    parse_interactive_brokers_positions_folder,
    parse_interactive_brokers_transactions,
    parse_interactive_brokers_transactions_folder,
)
from poems_parser import (
    add_stock_codes_to_positions,
    parse_poems_positions,
    parse_poems_transactions,
    parse_poems_workbooks,
)
from validation import print_duplicate_records_message


def ensure_folder_exists(folder_path: Path) -> None:
    """Create a folder when it does not already exist."""
    if folder_path.is_dir():
        return

    folder_path.mkdir(parents=True, exist_ok=True)
    print(f"Created missing folder: {folder_path}")


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


def save_dataframes_to_csv(
    transactions_df: pd.DataFrame, positions_df: pd.DataFrame, output_path: Path
) -> None:
    """Save the final dataframes as dated CSV files in the output folder."""
    ensure_folder_exists(output_path)
    today = date.today().isoformat()

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


def build_monthly_position_totals(
    workbooks: list[Path], csv_files: list[Path]
) -> pd.DataFrame:
    """Build monthly total market value by broker and currency from each snapshot."""
    records: list[dict[str, object]] = []

    for workbook_path in workbooks:
        transactions = parse_poems_transactions(workbook_path)
        if transactions.empty:
            continue

        positions = parse_poems_positions(workbook_path)
        positions = add_stock_codes_to_positions(positions, transactions)
        month = transactions["transaction_date"].max().to_period("M").to_timestamp()
        position_totals = positions.groupby("currency", dropna=False)["market_value"].sum()
        for currency, market_value in position_totals.items():
            records.append(
                {
                    "month": month,
                    "series": f"poems - {currency}",
                    "market_value": market_value,
                }
            )

    for csv_path in csv_files:
        transactions = parse_interactive_brokers_transactions(csv_path)
        if transactions.empty:
            continue

        positions = parse_interactive_brokers_positions(csv_path)
        month = transactions["transaction_date"].max().to_period("M").to_timestamp()
        position_totals = positions.groupby("currency", dropna=False)["market_value"].sum()
        for currency, market_value in position_totals.items():
            records.append(
                {
                    "month": month,
                    "series": f"interactive brokers - {currency}",
                    "market_value": market_value,
                }
            )

    if not records:
        return pd.DataFrame(columns=["month", "series", "market_value"])

    monthly_totals = pd.DataFrame(records)
    return (
        monthly_totals.groupby(["month", "series"], as_index=False)["market_value"]
        .sum()
        .sort_values(["month", "series"], ignore_index=True)
    )


def save_monthly_position_chart(
    monthly_totals: pd.DataFrame, output_path: Path
) -> None:
    """Save a line chart of monthly total market value by broker and currency."""
    if monthly_totals.empty:
        print("No monthly investment position data found. Skipping line chart.")
        return

    os.environ.setdefault(
        "MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache")
    )
    import matplotlib.pyplot as plt

    ensure_folder_exists(output_path)
    chart_file = output_path / f"investment_positions_by_month_{date.today().isoformat()}.png"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_data = monthly_totals.pivot(
        index="month", columns="series", values="market_value"
    ).sort_index()
    ax = chart_data.plot(marker="o", linewidth=2, figsize=(10, 6))
    ax.set_title("Monthly Investment Position by Broker and Currency")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total market value")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Broker - Currency")
    plt.tight_layout()
    plt.savefig(chart_file, dpi=150)
    plt.close()

    print(f"{action} monthly investment position chart: {chart_file}")


def build_monthly_transaction_totals(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Build monthly total transaction amount by broker and currency."""
    if transactions_df.empty:
        return pd.DataFrame(columns=["month", "series", "transaction_amount"])

    monthly_transactions = transactions_df.copy()
    monthly_transactions["month"] = (
        pd.to_datetime(monthly_transactions["transaction_date"])
        .dt.to_period("M")
        .dt.to_timestamp()
    )
    monthly_transactions["transaction_amount"] = pd.to_numeric(
        monthly_transactions["transaction_amount"], errors="coerce"
    )
    monthly_transactions["series"] = (
        monthly_transactions["broker"].astype(str)
        + " - "
        + monthly_transactions["price_currency"].astype(str)
    )

    return (
        monthly_transactions.groupby(["month", "series"], as_index=False)[
            "transaction_amount"
        ]
        .sum()
        .sort_values(["month", "series"], ignore_index=True)
    )


def save_monthly_transaction_chart(
    monthly_totals: pd.DataFrame, output_path: Path
) -> None:
    """Save a line chart of monthly total transaction amount by broker and currency."""
    if monthly_totals.empty:
        print("No monthly transaction data found. Skipping line chart.")
        return

    os.environ.setdefault(
        "MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache")
    )
    import matplotlib.pyplot as plt

    ensure_folder_exists(output_path)
    chart_file = output_path / f"transactions_by_month_{date.today().isoformat()}.png"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_data = monthly_totals.pivot(
        index="month", columns="series", values="transaction_amount"
    ).sort_index()
    ax = chart_data.plot(marker="o", linewidth=2, figsize=(10, 6))
    ax.set_title("Monthly Transaction Amount by Broker and Currency")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total transaction amount")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Broker - Currency")
    plt.tight_layout()
    plt.savefig(chart_file, dpi=150)
    plt.close()

    print(f"{action} monthly transaction chart: {chart_file}")


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
        return positions_df.assign(sector=pd.Series(dtype="object"), geography=pd.Series(dtype="object"))

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


def save_position_distribution_pie_chart(
    positions_df: pd.DataFrame,
    category_column: str,
    chart_title: str,
    filename_prefix: str,
    output_path: Path,
) -> None:
    """Save currency-separated pie charts for a position category."""
    if positions_df.empty:
        print(f"No investment position data found. Skipping {chart_title.lower()} chart.")
        return

    os.environ.setdefault(
        "MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache")
    )
    import matplotlib.pyplot as plt

    ensure_folder_exists(output_path)
    chart_file = output_path / f"{filename_prefix}_{date.today().isoformat()}.png"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_positions = positions_df.copy()
    chart_positions["market_value"] = pd.to_numeric(
        chart_positions["market_value"], errors="coerce"
    )
    chart_positions = chart_positions.dropna(subset=["market_value"])
    totals = (
        chart_positions.groupby(["currency", category_column], as_index=False)[
            "market_value"
        ]
        .sum()
        .sort_values(["currency", "market_value"], ascending=[True, False])
    )
    if totals.empty:
        print(f"No chartable investment position data found. Skipping {chart_title.lower()} chart.")
        return

    currencies = totals["currency"].dropna().unique()
    fig, axes = plt.subplots(1, len(currencies), figsize=(7 * len(currencies), 7))
    if len(currencies) == 1:
        axes = [axes]
    fig.subplots_adjust(left=0.06, right=0.94, top=0.86, bottom=0.22, wspace=0.35)

    for axis, currency in zip(axes, currencies):
        currency_totals = totals[totals["currency"] == currency]
        currency_totals = aggregate_small_pie_slices(
            currency_totals, category_column, "market_value", threshold=0.10
        )
        wedges, _, _ = axis.pie(
            currency_totals["market_value"],
            autopct="%1.1f%%",
            pctdistance=0.72,
            startangle=90,
            radius=0.85,
        )
        axis.set_title(f"{currency}")
        axis.set_aspect("equal")

        axis.legend(
            wedges,
            currency_totals[category_column],
            title=category_column.replace("_", " ").title(),
            loc="upper center",
            bbox_to_anchor=(0.5, -0.08),
            fontsize=8,
        )

    fig.suptitle(chart_title)
    plt.savefig(chart_file, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"{action} {chart_title.lower()} chart: {chart_file}")


def aggregate_small_pie_slices(
    totals: pd.DataFrame,
    category_column: str,
    value_column: str,
    threshold: float,
) -> pd.DataFrame:
    """Aggregate pie slices below the percentage threshold into Others."""
    total_value = totals[value_column].sum()
    if total_value <= 0:
        return totals

    totals = totals.copy()
    totals["percentage"] = totals[value_column] / total_value
    small_slices = totals["percentage"] < threshold
    if not small_slices.any():
        return totals.drop(columns=["percentage"])

    large_totals = totals.loc[~small_slices].drop(columns=["percentage"])
    others_total = totals.loc[small_slices, value_column].sum()
    if others_total <= 0:
        return large_totals

    others_row = {column: pd.NA for column in large_totals.columns}
    others_row[category_column] = "Others"
    others_row[value_column] = others_total
    if "currency" in large_totals.columns and not totals["currency"].empty:
        others_row["currency"] = totals["currency"].iloc[0]

    return pd.concat([large_totals, pd.DataFrame([others_row])], ignore_index=True)


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
