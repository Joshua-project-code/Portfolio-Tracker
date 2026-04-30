# Portfolio Tracker

Guidance for future Claude Code sessions working in this repository.

## Project Purpose

Portfolio Tracker parses investment broker exports into standardized pandas DataFrames and saves CSV/chart outputs. It supports POEMS Excel workbooks and Interactive Brokers CSV activity statements.

The main workflow is:

1. Read broker files from sibling folders named `POEMS` and `Interactive Brokers`.
2. Parse transactions and current positions into shared schemas.
3. Print duplicate-row warnings and table previews.
4. Save dated CSV files and PNG charts into the sibling `Output` folder.

The Flask web app can also upload new POEMS workbook files and Interactive
Brokers CSV files into those sibling folders, then re-run the parser workflow
against all available files.

## Run Commands

Install dependencies:

```powershell
python -m pip install pandas openpyxl matplotlib flask
```

Run the web app from the project folder:

```powershell
python .\app.py
```

Run the parser from the project folder:

```powershell
python .\parse_broker_reports.py
```

Run with a custom broker root folder:

```powershell
python .\parse_broker_reports.py "C:\path\to\broker-root"
```

Quick syntax check for all Python files:

```powershell
python -m py_compile app.py report_runner.py parse_broker_reports.py validation.py stock_mapping.py stock_code_mapping.py poems_parser.py output_helpers.py interactive_brokers_parser.py file_helpers.py constants.py chart_helpers.py
```

Run the automated test suite:

```powershell
python -m unittest discover -s tests -v
```

## File Map

- `app.py`: Flask web server for the Portfolio Tracker UI, upload API, and report API.
- `parse_broker_reports.py`: Main CLI entry point and user-friendly error handling.
- `report_runner.py`: Shared report workflow used by the CLI and web app, including broker file discovery, dataframe construction, console preview output, CSV/chart generation, and web response serialization.
- `templates/index.html`: Main web app page rendered by Flask.
- `static/app.js`: Frontend report fetch and rendering logic.
- `static/styles.css`: Web app styles.
- `constants.py`: Shared paths, extensions, and canonical output schemas.
- `file_helpers.py`: File discovery, folder creation, sheet lookup, column cleanup, and broker-name inference.
- `poems_parser.py`: POEMS Excel transaction and position parsing.
- `interactive_brokers_parser.py`: Interactive Brokers CSV section, transaction, and position parsing.
- `stock_mapping.py`: Loads `stock_mapping.csv` and adds sector/geography metadata to positions.
- `stock_code_mapping.py`: Builds and persists project-root `stock_code_mapping.csv`, mapping stock codes to latest stock names and retaining old stock names when names change.
- `chart_helpers.py`: Builds monthly summaries and saves line/pie charts.
- `output_helpers.py`: Writes dated CSV output files.
- `validation.py`: Prints duplicate full-row warnings.
- `stock_mapping.csv`: User-editable stock-to-sector/geography mapping.
- `tests/test_project.py`: Automated unittest coverage for parser helpers, broker parsers, report workflow helpers, output helpers, stock mapping, chart aggregation, validation output, and Flask routes.
- `testapp.md`: Test case catalogue with each test's description and expected observed output.

## Data Contracts

Transactions should use `TRANSACTION_COLUMNS` from `constants.py`:

```text
broker, transaction_date, stock_name, stock_code, transaction_price,
price_currency, units, transaction_amount, transaction_type
```

Positions should use `POSITION_COLUMNS` from `constants.py`:

```text
broker, stock_name, stock_code, currency, quantity, average_cost_price,
last_done_price, market_value, total_cost, unrealized_pl
```

When adding parser logic, return DataFrames reindexed to these schemas so downstream output and chart helpers keep working.

## Local Folders And Generated Files

The project expects this sibling-folder layout:

```text
Vibe Coding/
+-- POEMS/
+-- Interactive Brokers/
+-- Output/
+-- Portfolio Tracker/
```

Do not commit broker exports or generated outputs. `.gitignore` already excludes local broker folders, `Output`, Python caches, virtual environments, and Matplotlib cache files.

## Coding Guidelines

- Prefer small, direct changes that follow the current module boundaries.
- Use a TDD approach for new features: add or update the corresponding test case first, confirm it captures the intended behavior, then implement the feature.
- All new features and behavior changes should have corresponding automated test cases unless there is a clear documented reason they cannot be tested.
- Implement exception handling where it is needed, especially around file input, parsing, and output writing. Error messages should be user-friendly and actionable rather than raw technical tracebacks.
- Add or preserve docstrings for all functions, including new helper functions.
- Add or preserve a paragraph of comments at the top of every Python file describing what that file is about and which functions or constants it contains.
- Keep parser behavior user-friendly: when possible, print clear messages instead of raw tracebacks from the main script.
- Preserve the shared transaction and position schemas unless the user explicitly asks to change output columns.
- Use pandas operations for tabular parsing and transformation.
- Keep broker-specific parsing inside the broker parser modules.
- Keep chart generation inside `chart_helpers.py`.
- Keep filesystem path and discovery logic inside `file_helpers.py`.
- Avoid broad refactors unless needed for the requested change.
- Keep all Markdown documentation up to date when implementing changes,
  especially `README.md`, `PYTHON_FILES.md`, `testapp.md`, and this `CLAUDE.md` guidance.
  If behavior, commands, dependencies, file structure, or user workflows change,
  update the relevant Markdown files in the same change.
- Keep `testapp.md` updated whenever tests are added, removed, renamed, or materially changed. Each catalogue entry should include the test case description and expected observed output.
- If adding new output files, update `README.md` and `.gitignore` if appropriate.

## Verification

For low-risk edits, run `python -m py_compile` on the touched Python files.

For all feature work and parser behavior changes, run:

```powershell
python -m unittest discover -s tests -v
```

For parser or chart behavior changes, run:

```powershell
python .\parse_broker_reports.py
```

If broker files are not available locally, state that runtime verification could not be completed and describe what was checked instead.
