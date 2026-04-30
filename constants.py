# This module defines project-wide constants shared by the parser modules. It
# contains default folder and file paths, supported Excel and CSV extensions,
# and the canonical TRANSACTION_COLUMNS and POSITION_COLUMNS schemas used when
# constructing output DataFrames.

from __future__ import annotations

from pathlib import Path


DEFAULT_ROOT_PATH = Path(__file__).resolve().parent
DEFAULT_BROKER_ROOT_PATH = DEFAULT_ROOT_PATH.parent
DEFAULT_POEMS_PATH = DEFAULT_BROKER_ROOT_PATH / "POEMS"
DEFAULT_INTERACTIVE_BROKERS_PATH = DEFAULT_BROKER_ROOT_PATH / "Interactive Brokers"
DEFAULT_OUTPUT_PATH = DEFAULT_ROOT_PATH.parent / "Output"
DEFAULT_STOCK_MAPPING_PATH = DEFAULT_ROOT_PATH / "stock_mapping.csv"
DEFAULT_STOCK_CODE_MAPPING_PATH = DEFAULT_ROOT_PATH / "stock_code_mapping.csv"

EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
CSV_EXTENSIONS = {".csv"}

TRANSACTION_COLUMNS = [
    "broker",
    "transaction_date",
    "stock_name",
    "stock_code",
    "transaction_price",
    "price_currency",
    "units",
    "transaction_amount",
    "transaction_type",
]

POSITION_COLUMNS = [
    "broker",
    "stock_name",
    "stock_code",
    "currency",
    "quantity",
    "average_cost_price",
    "last_done_price",
    "market_value",
    "total_cost",
    "unrealized_pl",
]
