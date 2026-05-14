# Runtime DataFrames

This file lists DataFrames created during the Portfolio Tracker runtime workflow.

## Core report workflow (`portfolio_tracker/report_runner.py`)

- `poems_transactions_df`: POEMS transactions from all detected workbooks.
- `poems_positions_df`: POEMS latest positions snapshot.
- `ib_transactions_df`: Interactive Brokers transactions from CSV folder.
- `ib_positions_df`: Interactive Brokers latest positions snapshot.
- `transactions_df`: Combined POEMS + IB transactions, sorted by `transaction_date`.
- `positions_df`: Combined POEMS + IB positions, sorted by `market_value`.
- `monthly_position_totals_df`: Monthly position totals built once per report run and reused for chart generation and performance metrics.
- `stock_code_mapping_df`: Persisted/returned stock code mapping dataframe.
- `country_positions_df`: Positions after filling missing stock codes from mapping.
- `country_exposure_df`: Per-position country exposure values.
- `country_exposure_totals_df`: Country totals by currency.
- `monthly_totals_df`: Monthly position totals for line charts.
- `monthly_transactions_df`: Monthly transaction totals for line charts.
- `stock_mapping_df`: User-provided stock-code mapping (`sector`, `geography`).
- `mapped_positions_df`: Positions enriched with `sector` and `geography`.
- `table` (`dataframe_table`): Copy of input dataframe for JSON-safe serialization.

## Portfolio performance metrics (`portfolio_tracker/performance_metrics.py`)

- `daily_flows`: Normalized daily investor cash-flow dataframe by currency (`buy` as outflow, `sell` as inflow).
- `positions`: Positions copy with normalized currency values and numeric `market_value` / `total_cost` fields.
- `ending_values`: Current market value totals by currency.
- `cost_basis_values`: Current total-cost basis by currency.
- `currency_flows`: Currency-specific subset of normalized investor cash flows.
- `currency_valuations`: Currency-specific subset of valuation points used for assumptions and TWR.
- `return_flows`: Currency-specific cash-flow dataframe used for IRR/TWR, including an assumed initial outflow when transaction history is incomplete.
- `rows`: Per-holding metric output rows (`annualized_irr`, `simple_return`, `time_weighted_return`, `cagr`, `assumption_note`, `assumption_rule`, `assumption_debug`) for stocks/ETFs in current positions.
- `assumption`: Per-currency inferred missing-history assumption built from cost basis, observed buy outflows, observed sell inflows, and available valuation/transaction dates.
- `assumption_rule`: Explicit holding-level completeness rule outcome:
  `unit_coverage_complete`, `cash_coverage_complete`, or `missing_initial_investment`.
- `assumption_debug`: Human-readable explanation used by the web app hover popover.

## Report output warnings (`portfolio_tracker/report_runner.py`)

- `warnings`: Non-fatal output-save warnings included in report payload when
  CSV/chart output files are locked or otherwise not writable.
- `report["warnings"]`: UI-facing warning list rendered in the dashboard run
  warnings panel after each run.
- `flows`: Currency-specific external cash-flow dataframe used by TWR with exact transaction dates.
- `period_flows`: External cash flows that fall inside one valuation-to-valuation TWR sub-period.
- `current_rows`: Month-aligned current portfolio values by currency.
- `valuations`: Month-end valuation points by currency from available position snapshots.
- `valuation_points`: Month-end valuation table used to estimate chained Modified Dietz TWR.

## POEMS parser (`portfolio_tracker/poems_parser.py`)

- `raw`: Raw POEMS transaction worksheet.
- `positions`: Raw/transformed POEMS positions worksheet.
- `transactions`: Parsed POEMS transactions per workbook.
- `latest_positions`: Latest POEMS positions snapshot selected across workbooks.
- `transactions_df`: Concatenated POEMS transactions across workbooks.
- `stock_code_by_name`: Series lookup used to infer missing position stock codes.

## Interactive Brokers parser (`portfolio_tracker/interactive_brokers_parser.py`)

- `raw`: Raw IB activity CSV.
- `header_rows`: Header rows for a requested IB section.
- `data_rows`: Data rows for a requested IB section.
- `section`: Extracted IB section dataframe (e.g., Trades/Open Positions).
- `instruments`: Financial Instrument Information section dataframe.
- `trades`: Extracted `Trades` section.
- `order_rows`: Filtered stock order rows used for transactions.
- `positions`: Extracted `Open Positions` section.
- `position_rows`: Filtered summary rows used for positions.
- `transactions`: Parsed IB transactions per CSV.
- `latest_positions`: Latest IB positions snapshot selected across CSV files.

## Chart helpers (`portfolio_tracker/chart_helpers.py`)

- `positions`: Workbook-level POEMS positions used for monthly totals.
- `transactions`: Workbook/CSV-level transactions used for month selection.
- `position_totals`: Grouped totals by currency for each snapshot.
- `monthly_totals`: Dataframe built from monthly position records.
- `monthly_transactions`: Working dataframe with month/series for transaction totals.
- `chart_data`: Copy of monthly totals for plotting.
- `chart_positions`: Positions copy coerced for pie charting.
- `totals`: Grouped currency/category pie totals.
- `currency_totals`: Per-currency pie slice totals.
- `chart_file`: Per-currency chart output file path for sector/geography distribution charts.
- `large_totals`: Pie slices above threshold.

## ETF country exposure (`portfolio_tracker/etf_country_exposure.py`)

- `matrix`: Loaded ETF-country matrix.
- `exposure`: Positions subset for exposure processing.
- `joined`: Exposure dataframe merged with matrix percentages.
- `totals`: Melted/grouped country totals.
- `chart_totals`: Country totals prepared for charting.
- `currency_totals`: Per-currency country totals for pie chart.
- `sorted_totals`: Country totals sorted descending for slice selection.
- `visible_totals`: Top slices retained before `Others`.
- `positions`: Positions copy when filling missing stock codes.

## Stock mapping (`portfolio_tracker/stock_mapping.py`)

- `mapping`: Loaded/normalized `stock_mapping.csv`.
- `positions`: Positions copy enriched by merge with mapping metadata.
- `unmapped`: Series/DataFrame view of stock codes missing mapping coverage.

## Stock code mapping (`portfolio_tracker/stock_code_mapping.py`)

- `frame`: Normalized stock code/name pairs extracted per input dataframe.
- `mapping`: Loaded existing mapping or final mapping to save.
- `current_pairs`: Current runtime stock code/name pairs from parsed data.
- `existing_mapping`: Previously persisted stock code mapping.

## Notes

- Some names (e.g., `raw`, `positions`, `totals`, `mapping`) are reused in different modules/functions with different scopes.
- This file is intentionally implementation-focused; update it whenever DataFrame creation, naming, or flow changes.
