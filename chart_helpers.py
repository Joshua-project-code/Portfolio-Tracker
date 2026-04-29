# This module builds chart-ready summaries and saves Matplotlib chart images for
# broker positions and transactions. It contains helpers for the Matplotlib
# cache directory, monthly position and transaction totals, monthly line charts,
# currency-separated position distribution pie charts, and aggregation of small
# pie slices into an Others category.

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd

from file_helpers import ensure_folder_exists
from interactive_brokers_parser import (
    parse_interactive_brokers_positions,
    parse_interactive_brokers_transactions,
)
from poems_parser import (
    add_stock_codes_to_positions,
    parse_poems_positions,
    parse_poems_transactions,
)


def set_matplotlib_cache_dir() -> None:
    """Keep Matplotlib cache files inside the project workspace."""
    os.environ.setdefault(
        "MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache")
    )


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

    set_matplotlib_cache_dir()
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

    set_matplotlib_cache_dir()
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

    set_matplotlib_cache_dir()
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
