# Portfolio Tracker

Portfolio Tracker parses investment transaction and position exports from broker reports into pandas dataframes.

It currently supports:

- POEMS Excel workbooks from the `POEMS` folder
- Interactive Brokers CSV activity statements from the `Interactive Brokers` folder

The main script combines the broker data into:

- `transactions_df`: stock buy/sell transaction history from POEMS and Interactive Brokers
- `positions_df`: current investment positions from POEMS and Interactive Brokers

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
|   +-- parse_broker_reports.py
|   +-- stock_mapping.csv
```

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

The project includes `stock_mapping.csv`, which maps each `stock_name` to:

- `sector`
- `geography`

The parser uses this mapping to create investment-position pie charts. If you
want to change a stock's sector or geography, or if a new stock appears as
`Unmapped`, update `stock_mapping.csv` directly.

## Install Dependencies

The script and web app require pandas, openpyxl, matplotlib, and Flask.

Run:

```powershell
python -m pip install pandas openpyxl matplotlib flask
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

## Run The Parser From The Console

From the project folder, run:

```powershell
python .\parse_broker_reports.py
```

The script will print:

- Number and filenames of POEMS workbooks loaded
- Number and filenames of Interactive Brokers CSV files loaded
- Top 20 transaction records sorted by transaction date
- Top 30 investment position records sorted by market value descending
- Duplicate-record warnings, if duplicates exist
- Monthly investment-position and transaction-amount line charts by broker and currency saved to `Output`
- Sector and geography investment-position pie charts by currency saved to `Output`; slices under 10% are grouped as `Others`

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
Output/
+-- transactions_2026-04-28.csv
+-- positions_2026-04-28.csv
+-- investment_positions_by_month_2026-04-28.png
+-- transactions_by_month_2026-04-28.png
+-- sector_distribution_2026-04-28.png
+-- geography_distribution_2026-04-28.png
```

## Optional Root Folder Argument

By default, the script reads broker files from the parent folder of this project.

You can also provide a different broker root folder that contains `POEMS` and `Interactive Brokers` subfolders:

```powershell
python .\parse_broker_reports.py "C:\path\to\your\folder"
```
