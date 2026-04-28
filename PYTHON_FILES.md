# Python File Reference

This file lists the Python modules in this project and what each one is used for.

| File | Purpose |
| --- | --- |
| `parse_broker_reports.py` | Main command-line entry point. Checks broker input folders, prompts when files are missing, combines POEMS and Interactive Brokers dataframes, prints previews and duplicate warnings, saves dated CSV outputs, creates monthly broker-and-currency line charts, and creates sector/geography pie charts from `stock_mapping.csv`. |
| `constants.py` | Defines shared paths, supported file extensions, and the standard transaction and position dataframe column schemas. |
| `file_helpers.py` | Provides reusable file and spreadsheet helpers, including workbook and CSV discovery, Excel sheet lookup, column-name cleanup, and broker-name inference from folder paths. |
| `poems_parser.py` | Parses POEMS Excel workbooks into the common transaction and position dataframe schemas. It also infers missing POEMS position stock codes from transaction rows where possible. |
| `interactive_brokers_parser.py` | Parses Interactive Brokers activity CSV files, extracting trades, open positions, and instrument descriptions into the common dataframe schemas. |
| `validation.py` | Contains validation/reporting helpers, currently used to print full-row duplicate records in the generated dataframes. |
