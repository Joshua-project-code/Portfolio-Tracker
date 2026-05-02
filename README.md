# Portfolio Tracker

Portfolio Tracker parses investment transaction and position exports from broker reports into pandas dataframes.

It currently supports:

- POEMS Excel workbooks from the `POEMS` folder
- Interactive Brokers CSV activity statements from the `Interactive Brokers` folder

The main script combines the broker data into:

- `transactions_df`: stock buy/sell transaction history from POEMS and Interactive Brokers
- `positions_df`: current investment positions from POEMS and Interactive Brokers
- `data/stock_code_mapping.csv`: a persisted mapping from stock code to latest stock
  name, with previous stock names retained when a broker reports a changed name
  for the same stock code
- country exposure outputs derived from `data/etf_country_matrix.csv`, where
  ETF and listed-holding country percentages are multiplied by current position
  market value

The script also checks both dataframes for duplicate full-row records and prints a warning if duplicates are found.

## Folder Setup

Place the broker files into these folders:

```text
Vibe Coding/
+-- POEMS/
|   +-- your-poems-export.xlsx
+-- Interactive Brokers/
|   +-- your-interactive-brokers-export.csv
+-- Output/
+-- Portfolio Tracker/
|   +-- app.py
|   +-- portfolio_tracker/
|   +-- data/
|   |   +-- stock_mapping.csv
|   |   +-- etf_country_matrix.csv
|   |   +-- stock_code_mapping.csv
|   +-- docs/
|   |   +-- WEBAPP_USER_GUIDE.md
|   |   +-- USER_STORIES.md
|   |   +-- PYTHON_FILES.md
|   |   +-- testapp.md
```

## Project Structure

The repository is organized so the root stays small and generated report output stays outside the package:

```text
Portfolio Tracker/
+-- app.py                         # Flask launcher
+-- portfolio_tracker/             # Application package
|   +-- static/                     # Web JavaScript and CSS
|   +-- templates/                  # Flask templates
+-- data/
|   +-- stock_mapping.csv           # Editable sector/geography mapping
|   +-- etf_country_matrix.csv      # Editable country exposure percentage matrix
|   +-- stock_code_mapping.csv      # Persisted generated stock-code/name history
+-- docs/
|   +-- PYTHON_FILES.md             # Module reference
|   +-- testapp.md                  # Test case catalogue
|   +-- WEBAPP_USER_GUIDE.md        # Web app and testing user guide
|   +-- USER_STORIES.md             # User stories, diagrams, and traceability
+-- tests/
|   +-- test_project.py             # Automated test suite
```

## Generated Files

The parser writes dated generated files to the sibling `Output` folder. These
report artifacts should not be committed:

- `../Output/transactions_YYYY-MM-DD.csv`
- `../Output/positions_YYYY-MM-DD.csv`
- `../Output/country_exposure_YYYY-MM-DD.csv`
- `../Output/country_exposure_totals_YYYY-MM-DD.csv`
- `../Output/seaborn_*.png` static chart files
- `../Output/country_exposure_pie_SGD_YYYY-MM-DD.png`
- `../Output/country_exposure_pie_USD_YYYY-MM-DD.png`
- `../Output/plotly_*.html` interactive Plotly chart files

The committed editable sector/geography mapping is `data/stock_mapping.csv`.
The persisted generated stock-code/name history is `data/stock_code_mapping.csv`;
it can be committed so future runs can recover known stock codes from current or
historical broker names.

### POEMS Files

Upload or copy POEMS Excel files into the `POEMS` folder.

Supported file extensions:

- `.xlsx`
- `.xlsm`
- `.xls`

If there are multiple POEMS workbooks in the folder, the script reads all of them for transactions.

For transactions, all POEMS workbooks are included. For investment positions, only the POEMS workbook with the latest parsed transaction date is used because that position sheet is the most recent snapshot.

### Interactive Brokers Files

Upload or copy Interactive Brokers CSV files into the `Interactive Brokers` folder.

Supported file extension:

- `.csv`

If there are multiple Interactive Brokers CSV files in the folder, the script reads all of them for transactions.

For transactions, all Interactive Brokers CSV files are included. For investment positions, only the Interactive Brokers CSV with the latest parsed trade date is used because that open-position section is the most recent snapshot.

Only stock trades are included in `transactions_df`. Foreign currency trades such as `USD.SGD` are excluded.

The Interactive Brokers CSV should include these sections:

- `Trades`
- `Open Positions`
- `Financial Instrument Information`

### Stock Mapping

The project includes `data/stock_mapping.csv`, which maps each `stock_name` to:

- `sector`
- `geography`

The parser uses this mapping to create investment-position pie charts. If you
want to change a stock's sector or geography, or if a new stock appears as
`Unmapped`, update `data/stock_mapping.csv` directly.

This file is separate from the generated `data/stock_code_mapping.csv`,
which is produced automatically from broker reports and should be treated as
parser output rather than a sector/geography classification file.

### Country Exposure Matrix

The project includes `data/etf_country_matrix.csv`, which maps stock codes to
country percentage weights for ETFs and individual listed holdings. The required
identifier columns are:

- `ETF Name`
- `Stock Code`

The file keeps the legacy `ETF Name` column name, but it can contain any holding
label. All remaining columns are treated as country percentage columns. During
each report run, the parser matches current positions to this matrix by stock
code, multiplies each country percentage by the position's `market_value`, and
writes:

- `country_exposure_YYYY-MM-DD.csv`: one row per position, with country columns
  containing absolute exposure values
- `country_exposure_totals_YYYY-MM-DD.csv`: country exposure summed by
  `currency` and `country`
- `country_exposure_pie_SGD_YYYY-MM-DD.png` and
  `country_exposure_pie_USD_YYYY-MM-DD.png`: country exposure pie charts with
  the top four countries shown separately and the remaining exposure grouped as
  `Others`

When a current position is missing a stock code, the workflow uses
`data/stock_code_mapping.csv` to recover known codes from current or historical
stock names before applying the ETF country matrix.

For single-country holdings, enter `100.0` under the appropriate country. For
example, a Singapore-listed REIT can be recorded as `100.0` under `Singapore`,
while an ETF whose components are all listed in Hong Kong can be recorded as
`100.0` under `Hong Kong`.

## Install Dependencies

The script, web app, and tests require pandas, openpyxl, matplotlib, seaborn, plotly, and Flask.

Run:

```powershell
python -m pip install -r requirements.txt
```

## Run The Web App

From the project folder, run:

```powershell
python .\app.py
```

Open the local Flask URL shown in the terminal, usually:

```text
http://127.0.0.1:5000
```

Click `Run Report` to parse the broker files and view:

- Loaded POEMS and Interactive Brokers files
- Scrollable transaction and investment-position tables
- Generated chart images
- Country exposure pie charts for SGD and USD in the Seaborn chart view
- Generated CSV output links
- The same parser messages that previously printed only to the console

The Charts section includes a `Seaborn` / `Plotly` toggle. Each report run
generates both chart sets. The Seaborn view is shown by default, and the
interactive Plotly view can be selected without re-running the report.
Both chart types use dashboard-oriented typography with right-side legends so
the plot area remains readable and legend text is not clipped.

The web tables format selected numeric columns to two decimal places and align
numeric cells to the right for readability. This display formatting does not
change the source data or generated CSV files.

Click `Upload Files` to add new broker exports from the web app:

- POEMS uploads accept `.xlsx`, `.xlsm`, and `.xls` files and save them to the sibling `POEMS` folder
- Interactive Brokers uploads accept `.csv` files and save them to the sibling `Interactive Brokers` folder
- After a successful upload, the web app automatically re-runs the report using all files in both broker folders

The maintenance buttons at the bottom of the web app help reset local files and
the browser view:

- `Delete Broker Files` asks for confirmation, deletes files from the sibling
  `POEMS` and `Interactive Brokers` folders, and updates only the input-file
  counts and lists. Existing tables, CSV links, and charts remain visible.
- `Delete Output Files` asks for confirmation, deletes files from the sibling
  `Output` folder, and updates the `Output CSV Files` section. Existing tables
  and chart images remain visible until you run another report or clear the
  screen.
- `Clear Screen` asks for confirmation and clears all displayed counts, input
  lists, CSV links, charts, tables, captions, and console text. It does not
  delete any files.

Click `Application Testing` at the bottom of the page to open the automated test page. The page lists
the catalogued test cases from `docs/testapp.md`, lets you run each test
individually, and includes a `Run All Tests` button with a pass-count summary.

See `docs/WEBAPP_USER_GUIDE.md` for the full web app and testing workflow.

## Run The Parser From The Console

From the project folder, run:

```powershell
python -m portfolio_tracker.parse_broker_reports
```

The script will print:

- Number and filenames of POEMS workbooks loaded
- Number and filenames of Interactive Brokers CSV files loaded
- Top 20 transaction records sorted by transaction date
- Top 30 investment position records sorted by market value descending
- Duplicate-record warnings, if duplicates exist
- Seaborn PNG and Plotly HTML monthly investment-position line charts by broker and currency saved to `Output`
- Seaborn PNG and Plotly HTML monthly transaction-amount line charts by broker and currency saved to `Output`
- Seaborn PNG and Plotly HTML sector and geography investment-position pie charts by currency saved to `Output`; slices under 10% are grouped as `Others`
- Country exposure CSV files saved to `Output`, including per-position country
  exposure and currency/country totals
- SGD and USD country exposure pie charts saved to `Output`; each chart shows
  up to five slices, with the final slice grouped as `Others`
- Chart titles, axes, ticks, legends, and pie percentages use role-specific font sizes for readability
- Line and pie chart legends are placed on the right side of the plot area
- A persistent `data/stock_code_mapping.csv` file saved with columns
  `stock_code`, `stock_name`, and `old_stock_names`

The script also saves the output CSV files into the parent-level `Output` folder
using today's date in the filename. If the `Output` folder does not exist, the
script creates it.
If an output file with the same generated filename already exists, the script
overwrites that file. Other existing files in the `Output` folder are left as-is.

If either broker folder does not exist, the script creates it. If either broker
folder has no supported files, the script prompts you to upload the required
files into that folder and press Enter. If there are still no files after you
press Enter, the script continues without that broker's data for the run.

Example output files:

```text
Vibe Coding/
+-- Output/
|   +-- transactions_2026-04-28.csv
|   +-- positions_2026-04-28.csv
|   +-- country_exposure_2026-04-28.csv
|   +-- country_exposure_totals_2026-04-28.csv
|   +-- seaborn_investment_positions_by_month_2026-04-28.png
|   +-- seaborn_transactions_by_month_2026-04-28.png
|   +-- seaborn_sector_distribution_2026-04-28.png
|   +-- seaborn_geography_distribution_2026-04-28.png
|   +-- country_exposure_pie_SGD_2026-04-28.png
|   +-- country_exposure_pie_USD_2026-04-28.png
|   +-- plotly_investment_positions_by_month_2026-04-28.html
|   +-- plotly_transactions_by_month_2026-04-28.html
|   +-- plotly_sector_distribution_2026-04-28.html
|   +-- plotly_geography_distribution_2026-04-28.html
+-- Portfolio Tracker/
|   +-- data/
|   |   +-- stock_code_mapping.csv
```

## Optional Root Folder Argument

By default, the script reads broker files from the parent folder of this project.

You can also provide a different broker root folder that contains `POEMS` and `Interactive Brokers` subfolders:

```powershell
python -m portfolio_tracker.parse_broker_reports "C:\path\to\your\folder"
```

## Run Automated Tests

From the project folder, run:

```powershell
python -m unittest discover -s tests -v
```

The `docs/testapp.md` file catalogues each automated test case, its description, and
the expected observed output.

## Documentation

Additional project documentation is in the `docs` folder:

- `docs/WEBAPP_USER_GUIDE.md`: web app usage, country exposure maintenance, and
  application testing workflow
- `docs/USER_STORIES.md`: retrospective user stories, acceptance criteria,
  Mermaid diagrams, and story-to-file traceability
- `docs/PYTHON_FILES.md`: Python module and related file reference
- `docs/testapp.md`: automated test case catalogue consumed by the Application
  Testing page
