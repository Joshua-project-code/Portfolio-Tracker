# This module is the command-line entry point for Portfolio Tracker. It
# contains main() and run_parser() for CLI argument handling, plus the
# user-friendly error helpers print_user_friendly_error() and
# get_user_friendly_error_message().

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .constants import DEFAULT_BROKER_ROOT_PATH
from .report_runner import run_report


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
        prog="Portfolio Tracker",
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

    run_report(args.root_path, prompt_for_missing_files=True)


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
            "python -m pip install pandas openpyxl matplotlib seaborn plotly flask"
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
