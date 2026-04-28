# Python File Reference

This file lists the Python modules in this project and what each one is used for.

| File | Purpose |
| --- | --- |
| `parse_broker_reports.py` | Main command-line entry point. Checks broker input folders, combines POEMS and Interactive Brokers dataframes, prints previews and duplicate warnings, and orchestrates CSV and chart output generation. |
| `constants.py` | Defines shared paths, supported file extensions, and the standard transaction and position dataframe column schemas. |
| `file_helpers.py` | Provides reusable file and spreadsheet helpers, including workbook and CSV discovery, Excel sheet lookup, column-name cleanup, and broker-name inference from folder paths. |
| `output_helpers.py` | Saves generated transaction and position dataframes to dated CSV files, overwriting only matching filenames. |
| `chart_helpers.py` | Builds and saves monthly line charts and sector/geography pie charts, including currency separation and small-slice aggregation into `Others`. |
| `stock_mapping.py` | Loads `stock_mapping.csv`, normalizes stock names, and enriches positions with sector and geography classifications. |
| `poems_parser.py` | Parses POEMS Excel workbooks into the common transaction and position dataframe schemas. It also infers missing POEMS position stock codes from transaction rows where possible. |
| `interactive_brokers_parser.py` | Parses Interactive Brokers activity CSV files, extracting trades, open positions, and instrument descriptions into the common dataframe schemas. |
| `validation.py` | Contains validation/reporting helpers, currently used to print full-row duplicate records in the generated dataframes. |
