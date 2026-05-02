# Portfolio Tracker Python File Reference

This file lists the Python modules in Portfolio Tracker and what each one is used for.

| File | Purpose |
| --- | --- |
| `app.py` | Project-root Flask launcher that imports `portfolio_tracker.web`. |
| `portfolio_tracker/web.py` | Flask web server. Serves the Portfolio Tracker UI and Application Testing page, handles broker file uploads, cleanup requests, report runs, automated tests, static asset versioning, and generated output files. |
| `portfolio_tracker/parse_broker_reports.py` | Main command-line entry point. Parses CLI arguments, runs the shared report workflow, and shows user-friendly errors. |
| `portfolio_tracker/report_runner.py` | Shared report workflow for the CLI and Flask app. Checks broker input folders, combines POEMS and Interactive Brokers dataframes, prints previews and duplicate warnings, saves CSV/chart outputs, and serializes full web table and chart-set response data. |
| `portfolio_tracker/constants.py` | Defines shared paths, supported file extensions, and the standard transaction and position dataframe column schemas. |
| `portfolio_tracker/etf_country_exposure.py` | Loads `data/etf_country_matrix.csv`, builds per-position country exposure values for ETFs and listed holdings, pivots them into currency/country totals, fills missing stock codes from the generated stock-code mapping, and saves SGD/USD country exposure pie charts. |
| `portfolio_tracker/file_helpers.py` | Provides reusable file and spreadsheet helpers, including workbook and CSV discovery, Excel sheet lookup, column-name cleanup, and broker-name inference from folder paths. |
| `portfolio_tracker/output_helpers.py` | Saves generated transaction and position dataframes to dated CSV files, using the report date when supplied and overwriting only matching filenames. |
| `portfolio_tracker/chart_helpers.py` | Builds chart-ready summaries and saves Seaborn PNG and Plotly HTML monthly line charts and sector/geography pie charts, including role-specific typography, right-side legends, currency separation, and small-slice aggregation into `Others`. |
| `portfolio_tracker/stock_mapping.py` | Loads `data/stock_mapping.csv`, normalizes stock names, and enriches positions with sector and geography classifications. |
| `portfolio_tracker/stock_code_mapping.py` | Builds and persists generated `data/stock_code_mapping.csv`, mapping immutable stock codes to the latest stock name while retaining historical stock names when names change. |
| `portfolio_tracker/poems_parser.py` | Parses POEMS Excel workbooks into the common transaction and position dataframe schemas. It also infers missing POEMS position stock codes from transaction rows where possible. |
| `portfolio_tracker/interactive_brokers_parser.py` | Parses Interactive Brokers activity CSV files, extracting trades, open positions, and instrument descriptions into the common dataframe schemas. |
| `portfolio_tracker/validation.py` | Contains validation/reporting helpers, currently used to print full-row duplicate records in the generated dataframes. |

## Related Non-Python Files

| File | Purpose |
| --- | --- |
| `portfolio_tracker/templates/index.html` | Main Portfolio Tracker web page. |
| `portfolio_tracker/templates/application_testing.html` | Application Testing web page. |
| `portfolio_tracker/static/app.js` | Frontend behavior for upload, report execution, Seaborn/Plotly chart-library toggling, cleanup confirmations, delete-result UI updates, charts including country exposure pies, CSV links, and tables. |
| `portfolio_tracker/static/testing.js` | Frontend behavior for listing, running, and displaying application test results. |
| `portfolio_tracker/static/styles.css` | Shared web app styling, including the dashboard font stack, layout, responsive tables, chart containers, and testing page styles. |
| `data/stock_mapping.csv` | Editable stock-to-sector/geography mapping used for pie chart enrichment. |
| `data/etf_country_matrix.csv` | Editable country exposure percentage matrix for ETFs and individual listed holdings, used to calculate absolute country exposure from position market values. |
| `data/stock_code_mapping.csv` | Persisted generated stock-code/name history created from broker reports. |
| `docs/WEBAPP_USER_GUIDE.md` | Web app user guide covering Portfolio Tracker usage, country exposure maintenance, and Application Testing workflows. |
| `docs/USER_STORIES.md` | Retrospective user stories, acceptance criteria, Mermaid workflow diagrams, and story-to-file traceability. |
| `docs/testapp.md` | Test case catalogue consumed by the Application Testing page. |
| `requirements.txt` | Python dependencies for running the app, parser, chart generation, and tests. |
