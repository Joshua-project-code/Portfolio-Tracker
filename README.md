# Portfolio Tracker

Portfolio Tracker parses investment transaction and position exports from broker reports into pandas dataframes.

It currently supports:

- POEMS Excel workbooks from the `POEMS` folder
- Interactive Brokers CSV activity statements from the `Interactive Brokers` folder

The main script combines the broker data into:

- `transactions_df`: stock buy/sell transaction history from POEMS and Interactive Brokers
- `positions_df`: current investment positions from POEMS and Interactive Brokers
- `stock_code_mapping.csv`: a persisted mapping from stock code to latest stock
  name, with previous stock names retained when a broker reports a changed name
  for the same stock code

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
|   +-- docs/
```

## Project Structure

The repository is organized so the root stays small:

```text
Portfolio Tracker/
+-- app.py                         # Flask launcher
+-- portfolio_tracker/             # Application package
|   +-- static/                     # Web JavaScript and CSS
|   +-- templates/                  # Flask templates
+-- data/
|   +-- stock_mapping.csv           # Editable sector/geography mapping
+-- docs/
|   +-- PYTHON_FILES.md             # Module reference
|   +-- testapp.md                  # Test case catalogue
+-- tests/
|   +-- test_project.py             # Automated test suite
+-- stock_code_mapping.csv          # Generated local stock-code/name history
```

## Generated Files

The parser writes generated files that should not be committed:

- `../Output/transactions_YYYY-MM-DD.csv`
- `../Output/positions_YYYY-MM-DD.csv`
- `../Output/*.png` chart files
- `stock_code_mapping.csv` in the project folder

The committed editable mapping is `data/stock_mapping.csv`. It is separate from
the generated `stock_code_mapping.csv`.

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

This file is separate from the generated project-root `stock_code_mapping.csv`,
which is produced automatically from broker reports and should be treated as
parser output rather than a sector/geography classification file.

## Install Dependencies

The script, web app, and tests require pandas, openpyxl, matplotlib, and Flask.

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
- Generated CSV output links
- The same parser messages that previously printed only to the console

The web tables format selected numeric columns to two decimal places and align
numeric cells to the right for readability. This display formatting does not
change the source data or generated CSV files.

Click `Upload Files` to add new broker exports from the web app:

- POEMS uploads accept `.xlsx`, `.xlsm`, and `.xls` files and save them to the sibling `POEMS` folder
- Interactive Brokers uploads accept `.csv` files and save them to the sibling `Interactive Brokers` folder
- After a successful upload, the web app automatically re-runs the report using all files in both broker folders

Click `Application Testing` to open the automated test page. The page lists
the catalogued test cases from `docs/testapp.md`, lets you run each test
individually, and includes a `Run All Tests` button with a pass-count summary.

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
- Monthly investment-position and transaction-amount line charts by broker and currency saved to `Output`
- Sector and geography investment-position pie charts by currency saved to `Output`; slices under 10% are grouped as `Others`
- A persistent `stock_code_mapping.csv` file saved to the project folder, with columns
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
|   +-- investment_positions_by_month_2026-04-28.png
|   +-- transactions_by_month_2026-04-28.png
|   +-- sector_distribution_2026-04-28.png
|   +-- geography_distribution_2026-04-28.png
+-- Portfolio Tracker/
|   +-- stock_code_mapping.csv
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
