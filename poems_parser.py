# This module parses POEMS Excel workbooks into the common transaction and
# position schemas used by the rest of the project. It contains
# parse_poems_transactions(), parse_poems_positions(),
# add_stock_codes_to_positions(), and parse_poems_workbooks(), plus the
# TRADE_PATTERN expression used to extract trade details from POEMS description
# text.

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from constants import POSITION_COLUMNS, TRANSACTION_COLUMNS
from file_helpers import clean_column_name, find_sheet_name, get_broker_name


TRADE_PATTERN = re.compile(
    r"^\s*(?P<transaction_type>BUY|SELL)\s+"
    r"(?P<stock_name>.+?)\s*,\s*"
    r"(?P<stock_code>[A-Z0-9]+)\s+"
    r"(?P<units>[\d,]+)\s+@\s+"
    r"(?P<price_currency>[A-Z]{3})\s*"
    r"(?P<transaction_price>[\d.]+)\s*$",
    re.IGNORECASE,
)


def parse_poems_transactions(workbook_path: Path) -> pd.DataFrame:
    """Parse POEMS transaction detail rows from one workbook."""
    sheet_name = find_sheet_name(workbook_path, "Transaction Details")
    raw = pd.read_excel(workbook_path, sheet_name=sheet_name)

    records: list[dict[str, object]] = []
    for _, row in raw.iterrows():
        description = str(row.get("Description", "")).strip()
        # POEMS stores trade attributes in a single description string.
        match = TRADE_PATTERN.match(description)
        if not match:
            continue

        data = match.groupdict()
        transaction_price = float(data["transaction_price"])
        units = int(data["units"].replace(",", ""))
        records.append(
            {
                "broker": get_broker_name(workbook_path),
                "transaction_date": pd.to_datetime(row["Date"], dayfirst=True),
                "stock_name": data["stock_name"].strip(),
                "stock_code": data["stock_code"].strip(),
                "transaction_price": transaction_price,
                "price_currency": data["price_currency"].upper(),
                "units": units,
                "transaction_amount": transaction_price * units,
                "transaction_type": data["transaction_type"].lower(),
            }
        )

    return pd.DataFrame(records, columns=TRANSACTION_COLUMNS)


def parse_poems_positions(workbook_path: Path) -> pd.DataFrame:
    """Parse POEMS investment positions from one workbook."""
    sheet_name = find_sheet_name(workbook_path, "Investment Positions")
    positions = pd.read_excel(workbook_path, sheet_name=sheet_name)
    positions.columns = [clean_column_name(column) for column in positions.columns]

    if "stock_name" in positions.columns:
        positions["stock_name"] = positions["stock_name"].astype(str).str.strip()

    positions.insert(0, "broker", get_broker_name(workbook_path))
    positions = positions.drop(columns=["quantity_on_loan"], errors="ignore")
    if "stock_code" not in positions.columns:
        # The POEMS positions sheet does not include stock codes directly.
        positions.insert(2, "stock_code", pd.NA)

    numeric_columns = [
        "quantity",
        "average_cost_price",
        "last_done_price",
        "market_value",
        "total_cost",
        "unrealized_pl",
    ]
    for column in numeric_columns:
        if column in positions.columns:
            positions[column] = pd.to_numeric(positions[column], errors="coerce")

    return positions.reindex(columns=POSITION_COLUMNS)


def add_stock_codes_to_positions(
    positions: pd.DataFrame, transactions: pd.DataFrame
) -> pd.DataFrame:
    """Fill missing POEMS position stock codes using matching transaction rows."""
    if positions.empty or transactions.empty:
        return positions
    if "stock_name" not in positions.columns or "stock_name" not in transactions.columns:
        return positions

    stock_code_by_name = (
        transactions.dropna(subset=["stock_name", "stock_code"])
        .drop_duplicates("stock_name")
        .set_index("stock_name")["stock_code"]
    )
    inferred_stock_codes = positions["stock_name"].map(stock_code_by_name)
    positions["stock_code"] = positions["stock_code"].combine_first(inferred_stock_codes)

    return positions


def parse_poems_workbooks(workbooks: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse all POEMS transactions and positions from the latest workbook only."""
    if not workbooks:
        return (
            pd.DataFrame(columns=TRANSACTION_COLUMNS),
            pd.DataFrame(columns=POSITION_COLUMNS),
        )

    transactions_frames: list[pd.DataFrame] = []
    latest_transaction_date = pd.NaT
    latest_positions = pd.DataFrame(columns=POSITION_COLUMNS)

    for workbook_path in workbooks:
        transactions = parse_poems_transactions(workbook_path)
        transactions_frames.append(transactions)

        if transactions.empty:
            continue

        workbook_latest_date = transactions["transaction_date"].max()
        if pd.isna(latest_transaction_date) or workbook_latest_date > latest_transaction_date:
            latest_transaction_date = workbook_latest_date
            positions = parse_poems_positions(workbook_path)
            latest_positions = add_stock_codes_to_positions(positions, transactions)

    transactions_df = pd.concat(transactions_frames, ignore_index=True)

    return transactions_df, latest_positions
