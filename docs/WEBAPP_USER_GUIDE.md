# Portfolio Tracker Web App User Guide

This guide covers the browser-based Portfolio Tracker workflow and the
application testing page.

## Prerequisites

Install the project dependencies from the `Portfolio Tracker` folder:

```powershell
python -m pip install -r requirements.txt
```

The web app reads broker source files from sibling folders next to the project:

```text
Vibe Coding 1/
+-- POEMS/
+-- Interactive Brokers/
+-- Output/
+-- Portfolio Tracker/
```

Supported source files:

- POEMS: `.xlsx`, `.xlsm`, `.xls`
- Interactive Brokers: `.csv`

## Start The Web App

From the `Portfolio Tracker` folder, run:

```powershell
python .\app.py
```

Open the local Flask URL shown in the terminal. By default, this is:

```text
http://127.0.0.1:5000
```

## Portfolio Tracker Workflow

### Upload Broker Files

1. Click `Upload Files`.
2. Select POEMS workbooks, Interactive Brokers CSVs, or both.
3. Click `Upload And Run`.

The files are saved into the configured sibling broker folders. After a
successful upload, the web app automatically runs the report using all files in
the broker folders.

### Run A Report

Click `Run Report` to parse the existing broker files without uploading new
files.

The report produces:

- input file counts and filenames
- transaction and position counts
- portfolio performance metrics
- chart images and interactive charts
- downloadable CSV links
- transaction and investment-position tables
- parser console output (on a separate Debug Console page)
- run-progress stepper states and elapsed timer during execution
- non-fatal warning panel when output artifacts cannot be written

Generated files are written to the sibling `Output` folder using the current
date in the filename.

The Input Files section keeps each broker file list to about five visible rows.
If more files are loaded, scroll inside the list to see the rest.

### Run Progress And Warnings

Each report run shows:

- `Run Progress` stepper (`Fetching report`, `Parsing and calculations`,
  `Rendering dashboard`, `Complete`)
- elapsed run timer
- `Run Warnings` panel when output-save issues occur (for example, locked files)

This lets the dashboard keep usable on-screen results even when some generated
files fail to save.

### Review Portfolio Performance

The `Portfolio Performance` section shows annualized IRR, simple return,
time-weighted return, and CAGR above the charts.

It also includes a per-holding (stocks/ETFs) return table with sortable
columns for IRR, SR, TWR, and CAGR.

The app keeps currencies separate because there is no FX conversion table in
the project. Simple return is based on current position `market_value` versus
observed and assumed invested capital. If the uploaded transaction files do not
cover the current position cost basis, the app assumes an initial investment
equal to the missing cost basis implied by current holdings, observed buys, and
observed sells. The assumed date comes from the earliest available month-end
position snapshot when that snapshot is the first evidence of the holding;
otherwise it comes from the day before the first observed transaction. The web
app lists the amount, date, and data basis below the metrics. If transaction
history covers the current position cost basis, IRR and time-weighted return
are calculated from reported data without adding an assumed starting
investment. Time-weighted return uses chained Modified Dietz sub-period returns
between available valuation snapshots, with exact transaction dates used to
weight cash flows inside each sub-period.

Assumptions are displayed as a numbered list:

1. Each currency with incomplete transaction history gets its own assumption.
2. The assumption text states the inferred amount, date, cost basis, observed
   buys, observed sells, and date source.
3. In `Per-Holding Returns (Stocks And ETFs)`, hover the `Assumptions` field
   for a debug popover that explains exactly why the row is flagged or not.
   You can also click the field and use `Copy` / `Close` actions in the
   popover.
4. Holding-level rule outcomes are:
   - `unit_coverage_complete`
   - `cash_coverage_complete`
   - `missing_initial_investment`

### Review Charts

The `Charts` section has two views:

- `Seaborn`: static PNG charts, including SGD and USD country exposure pie
  charts
- `Plotly`: interactive HTML charts for monthly and distribution views

Each report run generates both chart sets. Use the toggle without rerunning the
report.

Chart presentation details:

- Portfolio trend and transaction trend charts span full width for readability.
- Sector and geography distributions are split into separate charts per currency
  (for example, one USD chart and one SGD chart) instead of combined subplots.
- Country exposure pie charts show up to six slices, with the remaining
  exposure grouped into `Others`.

### Review CSV Outputs

The `Output CSV Files` section links to generated CSV files, including:

- `transactions_YYYY-MM-DD.csv`
- `positions_YYYY-MM-DD.csv`
- `country_exposure_YYYY-MM-DD.csv`
- `country_exposure_totals_YYYY-MM-DD.csv`
- `stock_code_mapping.csv`

`stock_code_mapping.csv` is stored in the project `data` folder and records the
latest stock-code/name mapping discovered from broker files.

### Table Productivity Controls

Both `Transaction Details` and `Investment Positions` include:

- `Reset Filters` (clears search and dropdown filters)
- `Columns` picker (show/hide visible columns)
- `Export Current View` (downloads currently filtered rows as CSV)
- explicit filtered-empty state messaging (`No rows match current filters.`)

`data/stock_mapping.csv` is the editable classification file used for chart
enrichment and is keyed by immutable `stock_code` with `sector` and
`geography` columns.

### Country Exposure Data

Country exposure is controlled by `data/etf_country_matrix.csv`.

The report matches each position's stock code against that matrix. Country
percentages are multiplied by the position `market_value` to produce absolute
country exposure values.

Use this file for both ETFs and individual listed holdings when you want them to
contribute to the country exposure chart. For example:

- a Singapore-listed REIT can be entered as `100.0` under `Singapore`
- an ETF with Hong Kong-listed components can be entered as `100.0` under
  `Hong Kong`
- a global ETF can use multiple country percentage columns

Rows without a matching stock code stay in `country_exposure_YYYY-MM-DD.csv`,
but they contribute zero to `country_exposure_totals_YYYY-MM-DD.csv` and the pie
charts.

### Admin Mode And Maintenance Actions

The dashboard header includes an `Admin Mode` button. Enter `ADMIN` to enable
admin mode. While enabled, the status card shows an `Admin Mode Active` badge
and the admin panel displays maintenance actions.

The admin panel includes:

- `Delete Broker Files`: deletes files from the sibling `POEMS` and
  `Interactive Brokers` folders. Existing on-screen report output remains until
  you rerun or clear the page.
- `Delete Output Files`: deletes generated files from the sibling `Output`
  folder. Existing on-screen tables and charts remain until you rerun or clear
  the page.
- `Clear Screen`: clears the browser display only. It does not delete source
  files or generated output files.

If generated output files are locked by another process, report generation
continues and returns non-fatal warnings instead of failing the full run.

Each delete action asks for confirmation before it runs.

### Debug Console

Click `Debug Console` at the bottom of the main page to open parser and runtime
messages on a separate page.

### Back To Top Button

All web pages include a floating `Back To Top` button that appears after you
scroll down.

## Application Testing

Click `Application Testing` at the bottom of the Portfolio Tracker page.

The testing page loads the catalogued test cases from `docs/testapp.md` and
shows each test case with:

- test ID
- unittest function name
- description
- expected observed output
- current result status

### Run All Tests In The Web App

Click `Run All Tests`.

The page calls the Flask testing API, runs:

```powershell
python -m unittest discover -s tests -v
```

and updates each test row as `passed` or `failed`. The summary shows how many
tests passed out of the total loaded catalogue.

### Run One Test In The Web App

Click `Run Test` on a specific test row.

The web app resolves the short test function name to the matching unittest ID
and runs only that test. Use this when you are checking one parser, chart, CSV,
or Flask behavior after a targeted change.

### Run Tests From The Terminal

From the project folder, run the full suite with:

```powershell
python -m unittest discover -s tests -v
```

Run the country exposure tests only with:

```powershell
python -m unittest tests.test_project.EtfCountryExposureTests -v
```

Run one known test with its fully qualified unittest path:

```powershell
python -m unittest tests.test_project.EtfCountryExposureTests.test_build_country_exposure_dataframe_multiplies_percentages_by_market_value -v
```

## Updating The Test Catalogue

The testing page reads test metadata from `docs/testapp.md`.

When a test is added, removed, renamed, or materially changed, update
`docs/testapp.md` in the same change. The web page depends on that catalogue for
the test list and expected-output descriptions.

## Troubleshooting

If the app shows no broker files, confirm that files are in the sibling `POEMS`
or `Interactive Brokers` folders, or upload them through the web page.

If a chart or CSV is missing, run the report again and inspect the `Debug
Console` page for parser errors.

If a holding appears in `country_exposure_YYYY-MM-DD.csv` with all zero country
values, add or correct its stock code row in `data/etf_country_matrix.csv`.

If tests fail in the web page, rerun the same test from the terminal with `-v`
to see the full unittest output.

## Recent Updates (2026-05-14)

- `Portfolio Performance` now shows an `As of YYYY-MM-DD` caption in the section header.
- Performance assumptions are now surfaced through `Attention Needed` and per-holding assumption details, instead of a separate assumptions list panel.
- In `Transaction Trends`, monthly transaction lines now include zero-value points for months with no transactions for a broker/currency series.
- `Application Testing` now shows a `Run Outcome` panel that lists failed and not-run test cases immediately after a run.
- `Debug Console` refresh now shows in-progress/success/failure state, last refreshed time, `Updated` vs `No changes`, and a short refresh history.

