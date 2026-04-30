from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app as flask_app
from chart_helpers import (
    aggregate_small_pie_slices,
    build_monthly_position_totals,
    build_monthly_transaction_totals,
    save_monthly_position_chart,
    save_position_distribution_pie_chart,
)
from constants import POSITION_COLUMNS, TRANSACTION_COLUMNS
from file_helpers import (
    clean_column_name,
    ensure_folder_exists,
    find_csv_files,
    find_sheet_name,
    find_workbooks,
    get_broker_name,
)
from interactive_brokers_parser import (
    get_interactive_brokers_instrument_names,
    get_interactive_brokers_section,
    parse_interactive_brokers_positions,
    parse_interactive_brokers_positions_folder,
    parse_interactive_brokers_transactions,
    parse_interactive_brokers_transactions_folder,
)
from output_helpers import save_dataframe_to_csv, save_dataframes_to_csv
from parse_broker_reports import get_user_friendly_error_message
from poems_parser import (
    add_stock_codes_to_positions,
    parse_poems_positions,
    parse_poems_transactions,
    parse_poems_workbooks,
)
from report_runner import (
    build_dataframes,
    dataframe_table,
    find_broker_files_for_report,
    format_table_value,
    get_generated_output_names,
    run_report_with_console_output,
    wait_for_broker_files,
)
from stock_mapping import (
    enrich_positions_with_mapping,
    load_stock_mapping,
    normalize_stock_name,
)
from validation import print_duplicate_records_message


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)


class WorkspaceTemporaryDirectory:
    """Create temporary test folders inside the writable project workspace."""

    def __init__(self, *args, **kwargs):
        self.name = str(TEST_TEMP_ROOT / f"tmp-{uuid.uuid4().hex}")

    def __enter__(self) -> str:
        Path(self.name).mkdir(parents=True, exist_ok=False)
        return self.name

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        shutil.rmtree(self.name, ignore_errors=True)


tempfile.TemporaryDirectory = WorkspaceTemporaryDirectory


def write_poems_workbook(path: Path, trade_date: str, market_value: float = 1234.5) -> None:
    """Create a minimal POEMS workbook accepted by the parser."""
    transactions = pd.DataFrame(
        {
            "Date": [trade_date, trade_date, trade_date],
            "Description": [
                "BUY Acme Corp, ACME 1,200 @ USD 10.50",
                "SELL Beta Ltd, BETA 50 @ SGD 2.25",
                "DIVIDEND Acme Corp",
            ],
        }
    )
    positions = pd.DataFrame(
        {
            "Stock Name": ["Acme Corp"],
            "Currency": ["USD"],
            "Quantity": ["1200"],
            "Average Cost Price": ["10.50"],
            "Last Done Price": ["11.00"],
            "Market Value": [market_value],
            "Total Cost": ["12600"],
            "Unrealized PL": ["600"],
            "Quantity On Loan": [0],
        }
    )
    with pd.ExcelWriter(path) as writer:
        transactions.to_excel(writer, sheet_name="Transaction Details", index=False)
        positions.to_excel(writer, sheet_name="Investment Positions", index=False)


def write_ib_csv(path: Path, trade_date: str, quantity: int = 10) -> None:
    """Create a minimal Interactive Brokers activity CSV accepted by the parser."""
    rows = [
        [
            "Financial Instrument Information",
            "Header",
            "Symbol",
            "Description",
        ],
        [
            "Financial Instrument Information",
            "Data",
            "AAPL",
            "Apple Inc",
        ],
        [
            "Trades",
            "Header",
            "DataDiscriminator",
            "Asset Category",
            "Symbol",
            "Date/Time",
            "Quantity",
            "T. Price",
            "Currency",
        ],
        [
            "Trades",
            "Data",
            "Order",
            "Stocks",
            "AAPL",
            f"{trade_date}, 10:15:00",
            str(quantity),
            "150.25",
            "usd",
        ],
        [
            "Trades",
            "Data",
            "Order",
            "Forex",
            "USD.SGD",
            f"{trade_date}, 10:20:00",
            "100",
            "1.35",
            "USD",
        ],
        [
            "Trades",
            "Data",
            "Total",
            "Stocks",
            "AAPL",
            f"{trade_date}, 10:30:00",
            "10",
            "150.25",
            "USD",
        ],
        [
            "Open Positions",
            "Header",
            "DataDiscriminator",
            "Symbol",
            "Currency",
            "Quantity",
            "Cost Price",
            "Close Price",
            "Value",
            "Cost Basis",
            "Unrealized P/L",
        ],
        [
            "Open Positions",
            "Data",
            "Summary",
            "AAPL",
            "usd",
            "10",
            "145.00",
            "155.00",
            "1550.00",
            "1450.00",
            "100.00",
        ],
        [
            "Open Positions",
            "Data",
            "Total",
            "",
            "usd",
            "10",
            "",
            "",
            "1550.00",
            "",
            "",
        ],
    ]
    pd.DataFrame(rows).to_csv(path, header=False, index=False)


class FileHelperTests(unittest.TestCase):
    def test_clean_column_name_strips_lowercases_and_removes_slashes(self) -> None:
        self.assertEqual(clean_column_name(" Average/Cost Price "), "averagecost_price")

    def test_find_sheet_name_returns_case_insensitive_prefix_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "sample.xlsx"
            write_poems_workbook(workbook, "01/04/2026")

            self.assertEqual(find_sheet_name(workbook, "transaction"), "Transaction Details")

    def test_find_sheet_name_raises_when_prefix_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "sample.xlsx"
            write_poems_workbook(workbook, "01/04/2026")

            with self.assertRaisesRegex(ValueError, "No sheet starting"):
                find_sheet_name(workbook, "Missing")

    def test_find_workbooks_returns_supported_files_and_skips_excel_lock_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            workbook = folder / "a.xlsx"
            ignored_lock = folder / "~$locked.xlsx"
            text_file = folder / "notes.txt"
            write_poems_workbook(workbook, "01/04/2026")
            ignored_lock.write_text("", encoding="utf-8")
            text_file.write_text("", encoding="utf-8")

            self.assertEqual(find_workbooks(folder), [workbook])

    def test_find_workbooks_accepts_a_single_excel_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "single.xlsx"
            write_poems_workbook(workbook, "01/04/2026")

            self.assertEqual(find_workbooks(workbook), [workbook])

    def test_find_workbooks_rejects_non_excel_file_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            text_file = Path(temp_dir) / "notes.txt"
            text_file.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not an Excel workbook"):
                find_workbooks(text_file)

    def test_find_workbooks_raises_for_missing_or_empty_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                find_workbooks(Path(temp_dir) / "missing")
            with self.assertRaisesRegex(FileNotFoundError, "No Excel workbooks"):
                find_workbooks(Path(temp_dir))

    def test_find_csv_files_returns_supported_files_from_file_or_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            csv_file = folder / "activity.CSV"
            csv_file.write_text("a,b\n1,2\n", encoding="utf-8")
            (folder / "notes.txt").write_text("", encoding="utf-8")

            self.assertEqual(find_csv_files(folder), [csv_file])
            self.assertEqual(find_csv_files(csv_file), [csv_file])

    def test_find_csv_files_rejects_non_csv_file_and_returns_empty_for_missing_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            text_file = Path(temp_dir) / "notes.txt"
            text_file.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not a CSV file"):
                find_csv_files(text_file)
            self.assertEqual(find_csv_files(Path(temp_dir) / "missing"), [])

    def test_ensure_folder_exists_creates_nested_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "a" / "b"
            ensure_folder_exists(folder)

            self.assertTrue(folder.is_dir())

    def test_get_broker_name_infers_known_parent_or_immediate_folder(self) -> None:
        self.assertEqual(get_broker_name(Path("root") / "POEMS" / "file.xlsx"), "poems")
        self.assertEqual(
            get_broker_name(Path("root") / "Interactive Brokers" / "file.csv"),
            "interactive brokers",
        )
        self.assertEqual(get_broker_name(Path("root") / "Other" / "file.csv"), "other")


class PoemsParserTests(unittest.TestCase):
    def test_parse_poems_transactions_extracts_trade_rows_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "POEMS" / "sample.xlsx"
            workbook.parent.mkdir()
            write_poems_workbook(workbook, "01/04/2026")

            parsed = parse_poems_transactions(workbook)

            self.assertEqual(parsed.columns.tolist(), TRANSACTION_COLUMNS)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed.loc[0, "broker"], "poems")
            self.assertEqual(parsed.loc[0, "stock_name"], "Acme Corp")
            self.assertEqual(parsed.loc[0, "stock_code"], "ACME")
            self.assertEqual(parsed.loc[0, "units"], 1200)
            self.assertEqual(parsed.loc[0, "transaction_amount"], 12600.0)
            self.assertEqual(parsed.loc[1, "transaction_type"], "sell")

    def test_parse_poems_positions_normalizes_columns_and_drops_quantity_on_loan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "sample.xlsx"
            write_poems_workbook(workbook, "01/04/2026")

            parsed = parse_poems_positions(workbook)

            self.assertEqual(parsed.columns.tolist(), POSITION_COLUMNS)
            self.assertTrue(pd.isna(parsed.loc[0, "stock_code"]))
            self.assertEqual(parsed.loc[0, "market_value"], 1234.5)
            self.assertNotIn("quantity_on_loan", parsed.columns)

    def test_add_stock_codes_to_positions_fills_missing_codes_from_transactions(self) -> None:
        positions = pd.DataFrame({"stock_name": ["Acme Corp"], "stock_code": [pd.NA]})
        transactions = pd.DataFrame(
            {"stock_name": ["Acme Corp"], "stock_code": ["ACME"]}
        )

        updated = add_stock_codes_to_positions(positions, transactions)

        self.assertEqual(updated.loc[0, "stock_code"], "ACME")

    def test_add_stock_codes_to_positions_returns_unchanged_for_empty_inputs(self) -> None:
        positions = pd.DataFrame({"stock_name": ["Acme Corp"], "stock_code": [pd.NA]})

        updated = add_stock_codes_to_positions(positions.copy(), pd.DataFrame())

        self.assertTrue(pd.isna(updated.loc[0, "stock_code"]))

    def test_parse_poems_workbooks_combines_transactions_and_uses_latest_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "old.xlsx"
            second = Path(temp_dir) / "new.xlsx"
            write_poems_workbook(first, "01/03/2026", market_value=100)
            write_poems_workbook(second, "01/04/2026", market_value=200)

            transactions, positions = parse_poems_workbooks([first, second])

            self.assertEqual(len(transactions), 4)
            self.assertEqual(positions.loc[0, "market_value"], 200)
            self.assertEqual(positions.loc[0, "stock_code"], "ACME")

    def test_parse_poems_workbooks_empty_input_returns_empty_schema_frames(self) -> None:
        transactions, positions = parse_poems_workbooks([])

        self.assertEqual(transactions.columns.tolist(), TRANSACTION_COLUMNS)
        self.assertEqual(positions.columns.tolist(), POSITION_COLUMNS)
        self.assertTrue(transactions.empty)
        self.assertTrue(positions.empty)


class InteractiveBrokersParserTests(unittest.TestCase):
    def test_get_interactive_brokers_section_extracts_named_section(self) -> None:
        raw = pd.DataFrame(
            [
                ["Trades", "Header", "Col A", "Col B"],
                ["Trades", "Data", "x", "y"],
            ]
        )

        section = get_interactive_brokers_section(raw, "Trades")

        self.assertEqual(section.columns.tolist(), ["Col A", "Col B"])
        self.assertEqual(section.iloc[0].tolist(), ["x", "y"])

    def test_get_interactive_brokers_section_raises_when_missing(self) -> None:
        with self.assertRaisesRegex(ValueError, "No 'Trades' header"):
            get_interactive_brokers_section(pd.DataFrame([["Other", "Header"]]), "Trades")

    def test_get_interactive_brokers_instrument_names_returns_mapping_or_empty(self) -> None:
        raw = pd.DataFrame(
            [
                ["Financial Instrument Information", "Header", "Symbol", "Description"],
                ["Financial Instrument Information", "Data", "AAPL", "Apple Inc"],
            ]
        )

        self.assertEqual(get_interactive_brokers_instrument_names(raw), {"AAPL": "Apple Inc"})
        self.assertEqual(
            get_interactive_brokers_instrument_names(pd.DataFrame([["Other", "Header"]])),
            {},
        )

    def test_parse_interactive_brokers_transactions_filters_to_stock_orders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file = Path(temp_dir) / "Interactive Brokers" / "activity.csv"
            csv_file.parent.mkdir()
            write_ib_csv(csv_file, "2026-04-01")

            parsed = parse_interactive_brokers_transactions(csv_file)

            self.assertEqual(parsed.columns.tolist(), TRANSACTION_COLUMNS)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed.loc[0, "broker"], "interactive brokers")
            self.assertEqual(parsed.loc[0, "stock_name"], "Apple Inc")
            self.assertEqual(parsed.loc[0, "price_currency"], "USD")
            self.assertEqual(parsed.loc[0, "transaction_type"], "buy")

    def test_parse_interactive_brokers_transactions_marks_negative_quantity_as_sell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file = Path(temp_dir) / "activity.csv"
            write_ib_csv(csv_file, "2026-04-01", quantity=-5)

            parsed = parse_interactive_brokers_transactions(csv_file)

            self.assertEqual(parsed.loc[0, "transaction_type"], "sell")
            self.assertEqual(parsed.loc[0, "transaction_amount"], -751.25)

    def test_parse_interactive_brokers_positions_filters_to_summary_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file = Path(temp_dir) / "activity.csv"
            write_ib_csv(csv_file, "2026-04-01")

            parsed = parse_interactive_brokers_positions(csv_file)

            self.assertEqual(parsed.columns.tolist(), POSITION_COLUMNS)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed.loc[0, "stock_name"], "Apple Inc")
            self.assertEqual(parsed.loc[0, "currency"], "USD")
            self.assertEqual(parsed.loc[0, "market_value"], 1550.0)

    def test_parse_interactive_brokers_transactions_folder_returns_empty_schema_without_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_interactive_brokers_transactions_folder(Path(temp_dir))

            self.assertEqual(parsed.columns.tolist(), TRANSACTION_COLUMNS)
            self.assertTrue(parsed.empty)

    def test_parse_interactive_brokers_positions_folder_uses_latest_trade_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            old_csv = folder / "old.csv"
            new_csv = folder / "new.csv"
            write_ib_csv(old_csv, "2026-03-01")
            write_ib_csv(new_csv, "2026-04-01")

            parsed = parse_interactive_brokers_positions_folder(folder)

            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed.loc[0, "market_value"], 1550.0)


class StockMappingTests(unittest.TestCase):
    def test_load_stock_mapping_returns_empty_mapping_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping = load_stock_mapping(Path(temp_dir) / "missing.csv")

            self.assertEqual(mapping.columns.tolist(), ["stock_name_key", "sector", "geography"])
            self.assertTrue(mapping.empty)

    def test_load_stock_mapping_validates_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_file = Path(temp_dir) / "stock_mapping.csv"
            pd.DataFrame({"stock_name": ["Acme"], "sector": ["Tech"]}).to_csv(
                mapping_file, index=False
            )

            with self.assertRaisesRegex(ValueError, "geography"):
                load_stock_mapping(mapping_file)

    def test_load_stock_mapping_normalizes_values_and_deduplicates_by_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_file = Path(temp_dir) / "stock_mapping.csv"
            pd.DataFrame(
                {
                    "stock_name": [" Acme Corp ", "ACME CORP"],
                    "sector": [" Tech ", None],
                    "geography": [None, "US"],
                }
            ).to_csv(mapping_file, index=False)

            mapping = load_stock_mapping(mapping_file)

            self.assertEqual(len(mapping), 1)
            self.assertEqual(mapping.loc[0, "stock_name_key"], "ACME CORP")
            self.assertEqual(mapping.loc[0, "sector"], "Tech")
            self.assertEqual(mapping.loc[0, "geography"], "Unmapped")

    def test_normalize_stock_name_uppercases_strips_and_handles_missing_values(self) -> None:
        result = normalize_stock_name(pd.Series([" acme ", None]))

        self.assertEqual(result.tolist(), ["ACME", ""])

    def test_enrich_positions_with_mapping_adds_sector_and_geography(self) -> None:
        positions = pd.DataFrame(
            {
                "stock_name": ["Acme Corp", "Unknown"],
                "market_value": [100, 50],
            }
        )
        mapping = pd.DataFrame(
            {
                "stock_name_key": ["ACME CORP"],
                "sector": ["Tech"],
                "geography": ["US"],
            }
        )

        enriched = enrich_positions_with_mapping(positions, mapping)

        self.assertEqual(enriched.loc[0, "sector"], "Tech")
        self.assertEqual(enriched.loc[0, "geography"], "US")
        self.assertEqual(enriched.loc[1, "sector"], "Unmapped")
        self.assertNotIn("stock_name_key", enriched.columns)

    def test_enrich_positions_with_mapping_empty_positions_returns_expected_columns(self) -> None:
        enriched = enrich_positions_with_mapping(
            pd.DataFrame(columns=["stock_name"]),
            pd.DataFrame(columns=["stock_name_key", "sector", "geography"]),
        )

        self.assertIn("sector", enriched.columns)
        self.assertIn("geography", enriched.columns)
        self.assertTrue(enriched.empty)


class ChartHelperTests(unittest.TestCase):
    def test_build_monthly_transaction_totals_groups_by_month_broker_and_currency(self) -> None:
        transactions = pd.DataFrame(
            {
                "transaction_date": ["2026-04-01", "2026-04-15", "2026-05-01"],
                "transaction_amount": [100, 50, 25],
                "broker": ["poems", "poems", "ib"],
                "price_currency": ["USD", "USD", "SGD"],
            }
        )

        monthly = build_monthly_transaction_totals(transactions)

        self.assertEqual(len(monthly), 2)
        self.assertEqual(monthly.loc[0, "transaction_amount"], 150)
        self.assertEqual(monthly.loc[0, "series"], "poems - USD")

    def test_build_monthly_transaction_totals_empty_input_returns_schema(self) -> None:
        monthly = build_monthly_transaction_totals(pd.DataFrame())

        self.assertEqual(monthly.columns.tolist(), ["month", "series", "transaction_amount"])
        self.assertTrue(monthly.empty)

    def test_aggregate_small_pie_slices_groups_values_below_threshold_as_others(self) -> None:
        totals = pd.DataFrame(
            {
                "currency": ["USD", "USD", "USD"],
                "sector": ["Large", "Small A", "Small B"],
                "market_value": [90, 5, 5],
            }
        )

        aggregated = aggregate_small_pie_slices(totals, "sector", "market_value", 0.10)

        self.assertEqual(aggregated["sector"].tolist(), ["Large", "Others"])
        self.assertEqual(aggregated.loc[1, "market_value"], 10)
        self.assertEqual(aggregated.loc[1, "currency"], "USD")

    def test_aggregate_small_pie_slices_returns_input_when_total_is_not_positive(self) -> None:
        totals = pd.DataFrame({"sector": ["A"], "market_value": [0]})

        aggregated = aggregate_small_pie_slices(totals, "sector", "market_value", 0.10)

        self.assertEqual(aggregated.equals(totals), True)

    def test_build_monthly_position_totals_combines_poems_and_ib_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            workbook = folder / "poems.xlsx"
            csv_file = folder / "ib.csv"
            write_poems_workbook(workbook, "01/04/2026", market_value=100)
            write_ib_csv(csv_file, "2026-04-02")

            monthly = build_monthly_position_totals([workbook], [csv_file])

            self.assertEqual(monthly["series"].tolist(), ["interactive brokers - USD", "poems - USD"])
            self.assertEqual(monthly["market_value"].tolist(), [1550.0, 100.0])

    def test_save_monthly_position_chart_skips_empty_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with redirect_stdout(output):
                save_monthly_position_chart(pd.DataFrame(), Path(temp_dir))

            self.assertIn("Skipping line chart", output.getvalue())
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_save_position_distribution_pie_chart_skips_empty_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with redirect_stdout(output):
                save_position_distribution_pie_chart(
                    pd.DataFrame(),
                    "sector",
                    "Sector Distribution",
                    "sector_distribution",
                    Path(temp_dir),
                )

            self.assertIn("Skipping sector distribution chart", output.getvalue())


class OutputAndValidationTests(unittest.TestCase):
    def test_save_dataframe_to_csv_creates_file_without_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "frame.csv"
            save_dataframe_to_csv(pd.DataFrame({"a": [1]}), output_file, "test dataframe")

            self.assertEqual(output_file.read_text(encoding="utf-8").strip(), "a\n1")

    def test_save_dataframes_to_csv_creates_dated_transaction_and_position_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)

            save_dataframes_to_csv(
                pd.DataFrame({"transaction": [1]}),
                pd.DataFrame({"position": [2]}),
                output_path,
            )

            files = sorted(path.name for path in output_path.iterdir())
            self.assertEqual(len(files), 2)
            self.assertTrue(files[0].startswith("positions_"))
            self.assertTrue(files[1].startswith("transactions_"))

    def test_print_duplicate_records_message_outputs_duplicate_rows_only(self) -> None:
        dataframe = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
        output = io.StringIO()

        with redirect_stdout(output):
            print_duplicate_records_message("sample", dataframe)

        self.assertIn("Duplicate records found in sample: 2 duplicated row(s).", output.getvalue())
        self.assertIn("1 x", output.getvalue())

    def test_print_duplicate_records_message_is_silent_without_duplicates(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            print_duplicate_records_message("sample", pd.DataFrame({"a": [1, 2]}))

        self.assertEqual(output.getvalue(), "")


class ReportRunnerTests(unittest.TestCase):
    def test_find_broker_files_for_report_returns_empty_and_prints_without_prompting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with redirect_stdout(output):
                files = find_broker_files_for_report(
                    "POEMS", Path(temp_dir) / "POEMS", "POEMS Excel workbook(s)", find_workbooks
                )

            self.assertEqual(files, [])
            self.assertIn("Continuing without POEMS data.", output.getvalue())

    def test_wait_for_broker_files_returns_files_after_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            workbook = folder / "sample.xlsx"

            def create_file_after_first_lookup(path: Path) -> list[Path]:
                if not workbook.exists():
                    return []
                return [workbook]

            write_poems_workbook(workbook, "01/04/2026")
            with patch("builtins.input", return_value=""):
                files = wait_for_broker_files(
                    "POEMS", folder, "POEMS Excel workbook(s)", create_file_after_first_lookup
                )

            self.assertEqual(files, [workbook])

    def test_build_dataframes_combines_and_sorts_transactions_and_positions(self) -> None:
        poems_transactions = pd.DataFrame(
            {
                **{column: [] for column in TRANSACTION_COLUMNS},
                "transaction_date": pd.to_datetime([]),
            }
        )
        poems_transactions = pd.DataFrame(
            {
                "broker": ["poems"],
                "transaction_date": [pd.Timestamp("2026-04-02")],
                "stock_name": ["B"],
                "stock_code": ["B"],
                "transaction_price": [1],
                "price_currency": ["USD"],
                "units": [1],
                "transaction_amount": [1],
                "transaction_type": ["buy"],
            }
        )
        poems_positions = pd.DataFrame(
            {
                "broker": ["poems"],
                "stock_name": ["B"],
                "stock_code": ["B"],
                "currency": ["USD"],
                "quantity": [1],
                "average_cost_price": [1],
                "last_done_price": [1],
                "market_value": [50],
                "total_cost": [1],
                "unrealized_pl": [0],
            }
        )
        ib_transactions = poems_transactions.copy()
        ib_transactions.loc[0, "broker"] = "ib"
        ib_transactions.loc[0, "transaction_date"] = pd.Timestamp("2026-04-01")
        ib_positions = poems_positions.copy()
        ib_positions.loc[0, "broker"] = "ib"
        ib_positions.loc[0, "market_value"] = 100

        with patch("report_runner.parse_poems_workbooks", return_value=(poems_transactions, poems_positions)):
            with patch(
                "report_runner.parse_interactive_brokers_transactions_folder",
                return_value=ib_transactions,
            ):
                with patch(
                    "report_runner.parse_interactive_brokers_positions_folder",
                    return_value=ib_positions,
                ):
                    transactions, positions = build_dataframes([], Path("ib"))

        self.assertEqual(transactions["broker"].tolist(), ["ib", "poems"])
        self.assertEqual(positions["broker"].tolist(), ["ib", "poems"])

    def test_dataframe_table_serializes_nan_timestamps_and_numpy_scalars(self) -> None:
        table = dataframe_table(
            pd.DataFrame(
                {
                    "date": [pd.Timestamp("2026-04-01"), pd.NaT],
                    "amount": [pd.Series([1]).iloc[0], None],
                }
            )
        )

        self.assertEqual(table["columns"], ["date", "amount"])
        self.assertEqual(table["rows"][0]["date"], "2026-04-01")
        self.assertEqual(table["rows"][1]["date"], "")
        self.assertEqual(table["rows"][1]["amount"], "")
        self.assertEqual(table["total_rows"], 2)

    def test_format_table_value_handles_isoformat_and_item_values(self) -> None:
        self.assertEqual(format_table_value(pd.Timestamp("2026-04-01")), "2026-04-01")
        self.assertEqual(format_table_value(pd.Series([7]).iloc[0]), 7)

    def test_get_generated_output_names_returns_existing_expected_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            today = "2026-04-30"
            (output_path / f"transactions_{today}.csv").write_text("", encoding="utf-8")
            (output_path / f"sector_distribution_{today}.png").write_text("", encoding="utf-8")

            with patch("report_runner.DEFAULT_OUTPUT_PATH", output_path):
                charts, csvs = get_generated_output_names(today)

            self.assertEqual(charts, [f"sector_distribution_{today}.png"])
            self.assertEqual(csvs, [f"transactions_{today}.csv"])

    def test_run_report_with_console_output_includes_captured_console_text(self) -> None:
        with patch("report_runner.run_report", return_value={"ok": True}) as run_report:
            report = run_report_with_console_output(Path("root"))

        self.assertEqual(report["console_output"], "")
        run_report.assert_called_once()


class ErrorMessageTests(unittest.TestCase):
    def test_user_friendly_error_messages_cover_common_exceptions(self) -> None:
        self.assertIn("permission was denied", get_user_friendly_error_message(PermissionError("x")))
        self.assertIn("could not be found", get_user_friendly_error_message(FileNotFoundError("x")))
        self.assertIn("not installed", get_user_friendly_error_message(ModuleNotFoundError("missing")))
        self.assertIn("required column", get_user_friendly_error_message(KeyError("stock_name")))
        self.assertIn("Please correct", get_user_friendly_error_message(ValueError("bad file")))
        self.assertIn("unexpected problem", get_user_friendly_error_message(RuntimeError("boom")))
        self.assertIn(
            "valid workbook",
            get_user_friendly_error_message(zipfile.BadZipFile("bad zip")),
        )


class FlaskAppTests(unittest.TestCase):
    def test_index_renders_default_paths(self) -> None:
        flask_app.app.config.update(TESTING=True)
        client = flask_app.app.test_client()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Portfolio Tracker", response.data)

    def test_upload_files_saves_supported_files_and_reports_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            poems_folder = root / "POEMS"
            ib_folder = root / "Interactive Brokers"
            patched_targets = {
                "poems_files": {
                    "folder": poems_folder,
                    "extensions": {".xlsx"},
                    "label": "POEMS",
                },
                "interactive_brokers_files": {
                    "folder": ib_folder,
                    "extensions": {".csv"},
                    "label": "Interactive Brokers",
                },
            }
            flask_app.app.config.update(TESTING=True)
            client = flask_app.app.test_client()

            with patch.object(flask_app, "UPLOAD_TARGETS", patched_targets):
                response = client.post(
                    "/api/upload-files",
                    data={
                        "poems_files": [
                            (io.BytesIO(b"workbook"), "../../unsafe.xlsx"),
                            (io.BytesIO(b"text"), "notes.txt"),
                        ],
                        "interactive_brokers_files": [
                            (io.BytesIO(b"csv"), "activity.csv"),
                        ],
                    },
                    content_type="multipart/form-data",
                )

            payload = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["saved_files"]["poems_files"], ["unsafe.xlsx"])
            self.assertEqual(payload["saved_files"]["interactive_brokers_files"], ["activity.csv"])
            self.assertEqual(payload["rejected_files"], ["notes.txt is not a supported POEMS file."])
            self.assertTrue((poems_folder / "unsafe.xlsx").is_file())
            self.assertTrue((ib_folder / "activity.csv").is_file())

    def test_upload_files_returns_400_when_no_supported_files_are_uploaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            patched_targets = {
                "poems_files": {
                    "folder": Path(temp_dir) / "POEMS",
                    "extensions": {".xlsx"},
                    "label": "POEMS",
                },
                "interactive_brokers_files": {
                    "folder": Path(temp_dir) / "Interactive Brokers",
                    "extensions": {".csv"},
                    "label": "Interactive Brokers",
                },
            }
            flask_app.app.config.update(TESTING=True)
            client = flask_app.app.test_client()

            with patch.object(flask_app, "UPLOAD_TARGETS", patched_targets):
                response = client.post(
                    "/api/upload-files",
                    data={"poems_files": [(io.BytesIO(b"text"), "notes.txt")]},
                    content_type="multipart/form-data",
                )

            payload = response.get_json()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(payload["error"], "No supported files were uploaded.")
            self.assertEqual(payload["rejected_files"], ["notes.txt is not a supported POEMS file."])

    def test_run_report_api_returns_report_json_on_success(self) -> None:
        flask_app.app.config.update(TESTING=True)
        client = flask_app.app.test_client()

        with patch.object(flask_app, "run_report_with_console_output", return_value={"ok": True}):
            response = client.get("/api/run-report")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_run_report_api_returns_user_friendly_error_on_failure(self) -> None:
        flask_app.app.config.update(TESTING=True)
        client = flask_app.app.test_client()

        with patch.object(flask_app, "run_report_with_console_output", side_effect=ValueError("bad input")):
            response = client.get("/api/run-report")

        payload = response.get_json()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(payload["error_type"], "ValueError")
        self.assertIn("bad input", payload["error"])


if __name__ == "__main__":
    unittest.main()
