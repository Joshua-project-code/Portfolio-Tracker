# This module parses Interactive Brokers activity CSV exports into the shared
# transaction and position schemas. It contains helpers to extract named CSV
# sections and instrument names, parse transaction and open-position rows from
# one file, and parse the corresponding data across an entire folder.

from __future__ import annotations

from pathlib import Path

import pandas as pd

from constants import POSITION_COLUMNS, TRANSACTION_COLUMNS
from file_helpers import find_csv_files, get_broker_name


def get_interactive_brokers_section(raw: pd.DataFrame, section_name: str) -> pd.DataFrame:
    """Extract one named section from an Interactive Brokers activity CSV."""
    header_rows = raw[(raw[0] == section_name) & (raw[1] == "Header")]
    if header_rows.empty:
        raise ValueError(f"No {section_name!r} header found in Interactive Brokers CSV")

    # IBKR activity CSVs are sectioned: column 0 is section name, column 1 is row type.
    headers = header_rows.iloc[0].dropna().tolist()[2:]
    data_rows = raw[(raw[0] == section_name) & (raw[1] == "Data")]
    section = data_rows.iloc[:, 2 : 2 + len(headers)].copy()
    section.columns = headers

    return section


def get_interactive_brokers_instrument_names(raw: pd.DataFrame) -> dict[str, str]:
    """Return a ticker-to-description mapping from the IBKR instrument section."""
    try:
        instruments = get_interactive_brokers_section(
            raw, "Financial Instrument Information"
        )
    except ValueError:
        return {}

    return {
        str(row["Symbol"]).strip(): str(row["Description"]).strip()
        for _, row in instruments.iterrows()
        if pd.notna(row.get("Symbol")) and pd.notna(row.get("Description"))
    }


def parse_interactive_brokers_transactions(csv_path: Path) -> pd.DataFrame:
    """Parse IBKR trade rows into the common transactions schema."""
    raw = pd.read_csv(csv_path, header=None)
    trades = get_interactive_brokers_section(raw, "Trades")
    instrument_names = get_interactive_brokers_instrument_names(raw)

    records: list[dict[str, object]] = []
    # SubTotal and Total rows summarize trades, so only Order rows become records.
    # Forex orders such as USD.SGD are excluded because transactions_df tracks stocks.
    order_rows = trades[
        (trades["DataDiscriminator"].astype(str).str.lower() == "order")
        & (trades["Asset Category"].astype(str).str.lower() == "stocks")
    ]
    for _, row in order_rows.iterrows():
        quantity = pd.to_numeric(row["Quantity"], errors="coerce")
        transaction_price = pd.to_numeric(row["T. Price"], errors="coerce")
        stock_code = str(row["Symbol"]).strip()
        records.append(
            {
                "broker": get_broker_name(csv_path),
                "transaction_date": pd.to_datetime(row["Date/Time"]).normalize(),
                "stock_name": instrument_names.get(stock_code, stock_code),
                "stock_code": stock_code,
                "transaction_price": transaction_price,
                "price_currency": str(row["Currency"]).strip().upper(),
                "units": quantity,
                "transaction_amount": transaction_price * quantity,
                "transaction_type": "buy" if quantity >= 0 else "sell",
            }
        )

    return pd.DataFrame(records, columns=TRANSACTION_COLUMNS)


def parse_interactive_brokers_positions(csv_path: Path) -> pd.DataFrame:
    """Parse IBKR open position rows into the common positions schema."""
    raw = pd.read_csv(csv_path, header=None)
    positions = get_interactive_brokers_section(raw, "Open Positions")
    instrument_names = get_interactive_brokers_instrument_names(raw)

    records: list[dict[str, object]] = []
    # Summary rows are the individual holdings; Total rows are rollups.
    position_rows = positions[
        positions["DataDiscriminator"].astype(str).str.lower() == "summary"
    ]
    for _, row in position_rows.iterrows():
        stock_code = str(row["Symbol"]).strip()
        records.append(
            {
                "broker": get_broker_name(csv_path),
                "stock_name": instrument_names.get(stock_code, stock_code),
                "stock_code": stock_code,
                "currency": str(row["Currency"]).strip().upper(),
                "quantity": pd.to_numeric(row["Quantity"], errors="coerce"),
                "average_cost_price": pd.to_numeric(row["Cost Price"], errors="coerce"),
                "last_done_price": pd.to_numeric(row["Close Price"], errors="coerce"),
                "market_value": pd.to_numeric(row["Value"], errors="coerce"),
                "total_cost": pd.to_numeric(row["Cost Basis"], errors="coerce"),
                "unrealized_pl": pd.to_numeric(row["Unrealized P/L"], errors="coerce"),
            }
        )

    return pd.DataFrame(records, columns=POSITION_COLUMNS)


def parse_interactive_brokers_transactions_folder(folder_path: Path) -> pd.DataFrame:
    """Parse and combine transaction rows from all IBKR CSV files in a folder."""
    csv_files = find_csv_files(folder_path)
    if not csv_files:
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)

    return pd.concat(
        [parse_interactive_brokers_transactions(csv_path) for csv_path in csv_files],
        ignore_index=True,
    )


def parse_interactive_brokers_positions_folder(folder_path: Path) -> pd.DataFrame:
    """Parse open positions from the IBKR CSV with the latest transaction date."""
    csv_files = find_csv_files(folder_path)
    if not csv_files:
        return pd.DataFrame(columns=POSITION_COLUMNS)

    latest_transaction_date = pd.NaT
    latest_positions = pd.DataFrame(columns=POSITION_COLUMNS)

    for csv_path in csv_files:
        transactions = parse_interactive_brokers_transactions(csv_path)
        if transactions.empty:
            continue

        csv_latest_date = transactions["transaction_date"].max()
        if pd.isna(latest_transaction_date) or csv_latest_date > latest_transaction_date:
            latest_transaction_date = csv_latest_date
            latest_positions = parse_interactive_brokers_positions(csv_path)

    return latest_positions
