# Test Case Catalogue

Run all tests from the project folder with:

```powershell
python -m unittest discover -s tests -v
```

The suite is implemented in `tests/test_project.py` and uses workspace-local temporary files so broker exports and generated outputs are not required.

| ID | Test case | Description | Expected observed output |
|---|---|---|---|
| TC-001 | `test_clean_column_name_strips_lowercases_and_removes_slashes` | Normalizes a source column name by trimming, lowercasing, removing slashes, and replacing spaces. | Returns `averagecost_price`. |
| TC-002 | `test_find_sheet_name_returns_case_insensitive_prefix_match` | Finds an Excel sheet by case-insensitive prefix. | Returns `Transaction Details`. |
| TC-003 | `test_find_sheet_name_raises_when_prefix_is_absent` | Handles a workbook with no matching sheet prefix. | Raises `ValueError` containing `No sheet starting`. |
| TC-004 | `test_find_workbooks_returns_supported_files_and_skips_excel_lock_files` | Discovers supported Excel files and ignores Excel lock files. | Returns only the real `.xlsx` workbook. |
| TC-005 | `test_find_workbooks_accepts_a_single_excel_file` | Accepts a direct Excel workbook path. | Returns a one-item list containing that workbook. |
| TC-006 | `test_find_workbooks_rejects_non_excel_file_input` | Rejects a direct non-Excel file path. | Raises `ValueError` containing `not an Excel workbook`. |
| TC-007 | `test_find_workbooks_raises_for_missing_or_empty_folder` | Handles missing and empty workbook folders. | Raises `FileNotFoundError` for both cases. |
| TC-008 | `test_find_csv_files_returns_supported_files_from_file_or_folder` | Discovers CSV files from a folder and direct CSV file path. | Returns only the `.CSV` file. |
| TC-009 | `test_find_csv_files_rejects_non_csv_file_and_returns_empty_for_missing_folder` | Rejects direct non-CSV files and tolerates missing CSV folders. | Raises `ValueError` for the text file and returns `[]` for the missing folder. |
| TC-010 | `test_ensure_folder_exists_creates_nested_folder` | Creates missing nested folders. | Target folder exists after the call. |
| TC-011 | `test_get_broker_name_infers_known_parent_or_immediate_folder` | Infers broker names from known or fallback parent folders. | Returns `poems`, `interactive brokers`, or the immediate folder name. |
| TC-012 | `test_parse_poems_transactions_extracts_trade_rows_and_schema` | Parses POEMS trade descriptions and ignores non-trade rows. | Returns two transaction rows in `TRANSACTION_COLUMNS` with parsed code, units, amount, and type. |
| TC-013 | `test_parse_poems_positions_normalizes_columns_and_drops_quantity_on_loan` | Parses POEMS positions, normalizes columns, and drops loan quantity. | Returns `POSITION_COLUMNS`, numeric market value, and blank stock code. |
| TC-014 | `test_add_stock_codes_to_positions_fills_missing_codes_from_transactions` | Infers missing POEMS position stock codes from transaction history. | Position stock code becomes `ACME`. |
| TC-015 | `test_add_stock_codes_to_positions_returns_unchanged_for_empty_inputs` | Leaves positions unchanged when transactions are empty. | Position stock code remains missing. |
| TC-016 | `test_parse_poems_workbooks_combines_transactions_and_uses_latest_positions` | Combines POEMS transactions across workbooks and selects latest positions. | Returns four transactions and the latest workbook's position value. |
| TC-017 | `test_parse_poems_workbooks_empty_input_returns_empty_schema_frames` | Handles no POEMS workbooks. | Returns empty transaction and position DataFrames with canonical schemas. |
| TC-018 | `test_get_interactive_brokers_section_extracts_named_section` | Extracts a named IBKR CSV section from header/data rows. | Returns a DataFrame with section headers and one data row. |
| TC-019 | `test_get_interactive_brokers_section_raises_when_missing` | Handles a missing IBKR section header. | Raises `ValueError` containing `No 'Trades' header`. |
| TC-020 | `test_get_interactive_brokers_instrument_names_returns_mapping_or_empty` | Builds ticker-to-description mappings when instrument data exists. | Returns `{"AAPL": "Apple Inc"}` or `{}` when the section is absent. |
| TC-021 | `test_parse_interactive_brokers_transactions_filters_to_stock_orders` | Parses only stock order rows from IBKR trades. | Returns one buy transaction for `Apple Inc`; forex and total rows are excluded. |
| TC-022 | `test_parse_interactive_brokers_transactions_marks_negative_quantity_as_sell` | Converts negative IBKR order quantities into sell transactions. | Transaction type is `sell` and amount is negative. |
| TC-023 | `test_parse_interactive_brokers_positions_filters_to_summary_rows` | Parses only IBKR open-position summary rows. | Returns one USD position for `Apple Inc` with market value `1550.0`. |
| TC-024 | `test_parse_interactive_brokers_transactions_folder_returns_empty_schema_without_csvs` | Handles an IBKR folder with no CSV files. | Returns an empty transaction DataFrame with `TRANSACTION_COLUMNS`. |
| TC-025 | `test_parse_interactive_brokers_positions_folder_uses_latest_trade_file` | Selects positions from the IBKR CSV with the latest trade date. | Returns the latest file's open-position snapshot. |
| TC-026 | `test_load_stock_mapping_returns_empty_mapping_when_file_missing` | Handles a missing stock mapping CSV. | Returns an empty mapping DataFrame with `stock_name_key`, `sector`, and `geography`. |
| TC-027 | `test_load_stock_mapping_validates_required_columns` | Validates required stock mapping columns. | Raises `ValueError` naming missing `geography`. |
| TC-028 | `test_load_stock_mapping_normalizes_values_and_deduplicates_by_key` | Normalizes stock mapping names, fills missing values, and deduplicates. | Returns one normalized `ACME CORP` mapping with filled `Unmapped` geography. |
| TC-029 | `test_normalize_stock_name_uppercases_strips_and_handles_missing_values` | Normalizes stock names for lookups. | Returns `["ACME", ""]`. |
| TC-030 | `test_enrich_positions_with_mapping_adds_sector_and_geography` | Adds sector/geography data to positions and flags unmapped rows. | Known stock gets mapped values; unknown stock gets `Unmapped`. |
| TC-031 | `test_enrich_positions_with_mapping_empty_positions_returns_expected_columns` | Handles empty positions during mapping enrichment. | Returns empty DataFrame with `sector` and `geography` columns. |
| TC-032 | `test_build_monthly_transaction_totals_groups_by_month_broker_and_currency` | Aggregates transaction amounts by month, broker, and currency. | April POEMS USD total is `150`; May IB SGD total is separate. |
| TC-033 | `test_build_monthly_transaction_totals_empty_input_returns_schema` | Handles empty transaction input. | Returns empty monthly transaction DataFrame with expected columns. |
| TC-034 | `test_aggregate_small_pie_slices_groups_values_below_threshold_as_others` | Groups small pie slices under the threshold. | Small categories combine into an `Others` row worth `10`. |
| TC-035 | `test_aggregate_small_pie_slices_returns_input_when_total_is_not_positive` | Avoids aggregation when total value is zero or negative. | Returns the original totals unchanged. |
| TC-036 | `test_build_monthly_position_totals_combines_poems_and_ib_snapshots` | Builds monthly position totals from POEMS and IBKR snapshot files. | Returns broker/currency series for both sources with summed market values. |
| TC-037 | `test_save_monthly_position_chart_skips_empty_data` | Skips position chart generation when there is no data. | Prints a skip message and creates no chart file. |
| TC-038 | `test_save_position_distribution_pie_chart_skips_empty_data` | Skips distribution pie chart generation when positions are empty. | Prints a skip message for the requested chart. |
| TC-039 | `test_save_dataframe_to_csv_creates_file_without_index` | Saves a DataFrame as CSV without pandas index. | CSV contains only `a` and `1`. |
| TC-040 | `test_save_dataframes_to_csv_creates_dated_transaction_and_position_files` | Saves both dated output CSVs. | Creates one `transactions_YYYY-MM-DD.csv` and one `positions_YYYY-MM-DD.csv`. |
| TC-041 | `test_print_duplicate_records_message_outputs_duplicate_rows_only` | Reports duplicated full rows. | Prints a duplicate warning with `2 duplicated row(s)` and the duplicate row content. |
| TC-042 | `test_print_duplicate_records_message_is_silent_without_duplicates` | Avoids output when no duplicate rows exist. | Prints nothing. |
| TC-043 | `test_find_broker_files_for_report_returns_empty_and_prints_without_prompting` | Non-interactive broker discovery handles missing files. | Returns `[]` and prints continuation messages. |
| TC-044 | `test_wait_for_broker_files_returns_files_after_prompt` | Interactive broker discovery can return files after prompting. | Returns the workbook list after the mocked prompt. |
| TC-045 | `test_build_dataframes_combines_and_sorts_transactions_and_positions` | Combines parser outputs and sorts final DataFrames. | Transactions sort by date ascending; positions sort by market value descending. |
| TC-046 | `test_dataframe_table_serializes_nan_timestamps_and_numpy_scalars` | Converts DataFrames into JSON-friendly table payloads. | Timestamps become dates, missing values become empty strings, and row count is preserved. |
| TC-047 | `test_format_table_value_handles_isoformat_and_item_values` | Formats pandas timestamps and scalar values. | Returns `2026-04-01` and native integer `7`. |
| TC-048 | `test_get_generated_output_names_returns_existing_expected_files_only` | Lists generated output files that exist for a date. | Returns only the matching existing chart and CSV names. |
| TC-049 | `test_run_report_with_console_output_includes_captured_console_text` | Captures console output around the report workflow. | Returned report includes a `console_output` field. |
| TC-050 | `test_user_friendly_error_messages_cover_common_exceptions` | Maps common exceptions to plain-language messages. | Each exception type returns an actionable user-facing message. |
| TC-051 | `test_index_renders_default_paths` | Renders the Flask homepage. | HTTP 200 response includes `Portfolio Tracker`. |
| TC-052 | `test_upload_files_saves_supported_files_and_reports_rejections` | Upload API saves supported POEMS/IBKR files and rejects unsupported files. | HTTP 200 with sanitized saved filenames and one rejection message. |
| TC-053 | `test_upload_files_returns_400_when_no_supported_files_are_uploaded` | Upload API handles requests with no supported files. | HTTP 400 with `No supported files were uploaded.` |
| TC-054 | `test_run_report_api_returns_report_json_on_success` | Report API returns workflow output on success. | HTTP 200 with the mocked report JSON. |
| TC-055 | `test_run_report_api_returns_user_friendly_error_on_failure` | Report API converts workflow exceptions into JSON errors. | HTTP 500 with `error_type` and friendly error text. |
| TC-056 | `test_application_testing_page_renders_test_runner_shell` | Renders the Application Testing page shell. | HTTP 200 response includes `Application Testing` and `Run All Tests`. |
| TC-057 | `test_tests_api_returns_catalogued_test_cases` | Returns the test catalogue from `testapp.md` as JSON. | HTTP 200 with catalogue entries including `TC-001` and descriptions. |
| TC-058 | `test_run_tests_api_runs_all_or_one_test_case` | Runs all tests or one named test case through the testing API. | HTTP 200 for both requests and the mocked test result is `passed`. |
