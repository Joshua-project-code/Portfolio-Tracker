const runButton = document.querySelector("#run-report");
const showUploadButton = document.querySelector("#show-upload");
const deleteBrokerFilesButton = document.querySelector("#delete-broker-files");
const deleteOutputFilesButton = document.querySelector("#delete-output-files");
const clearScreenButton = document.querySelector("#clear-screen");
const showSeabornChartsButton = document.querySelector("#show-seaborn-charts");
const showPlotlyChartsButton = document.querySelector("#show-plotly-charts");
const adminModeToggleButton = document.querySelector("#admin-mode-toggle");
const adminModePanel = document.querySelector("#admin-mode-panel");
const uploadPanel = document.querySelector("#upload-panel");
const uploadForm = document.querySelector("#upload-form");
const uploadSubmitButton = document.querySelector("#upload-submit");
const uploadMessage = document.querySelector("#upload-message");
const statusText = document.querySelector("#status-text");
const appNotice = document.querySelector("#app-notice");
const adminModeBadge = document.querySelector("#admin-mode-badge");
const transactionsSearchInput = document.querySelector("#transactions-search");
const positionsSearchInput = document.querySelector("#positions-search");
const transactionsBrokerFilter = document.querySelector("#transactions-broker-filter");
const transactionsCurrencyFilter = document.querySelector("#transactions-currency-filter");
const positionsBrokerFilter = document.querySelector("#positions-broker-filter");
const positionsCurrencyFilter = document.querySelector("#positions-currency-filter");
const rowDensitySelect = document.querySelector("#row-density");
const positionsRowDensitySelect = document.querySelector("#positions-row-density");
let currentChartMode = "seaborn";
let currentChartSets = {
  seaborn: [],
  plotly: [],
};
let currentChartCacheKey = "";
let holdingPerformanceSort = {
  column: "annualized_irr",
  direction: "desc",
};
let positionsSort = {
  column: "market_value",
  direction: "desc",
};
const DEFAULT_CONSOLE_MESSAGE = "Run the report to display parser output here.";
const CONSOLE_OUTPUT_STORAGE_KEY = "portfolio_tracker_console_output";
const ADMIN_MODE_CODE = "ADMIN";
const CHART_MODE_STORAGE_KEY = "portfolio_tracker_chart_mode";
let isAdminModeEnabled = false;
let transactionsData = { columns: [], rows: [], total_rows: 0 };
let positionsData = { columns: [], rows: [], total_rows: 0 };

function setAdminModeUiState(enabled) {
  isAdminModeEnabled = enabled;
  adminModePanel.hidden = !enabled;
  adminModeBadge.hidden = !enabled;
  adminModeToggleButton.textContent = enabled ? "Admin Mode Enabled" : "Admin Mode";
}

function setConsoleOutput(message) {
  const text = message || DEFAULT_CONSOLE_MESSAGE;
  try {
    window.localStorage.setItem(CONSOLE_OUTPUT_STORAGE_KEY, text);
  } catch (_error) {
    // Best effort only; continue rendering without local persistence.
  }
}

function setNotice(message, kind = "info") {
  if (!appNotice) {
    return;
  }
  if (!message) {
    appNotice.hidden = true;
    appNotice.textContent = "";
    appNotice.className = "notice-row";
    return;
  }
  appNotice.hidden = false;
  appNotice.textContent = message;
  appNotice.className = `notice-row ${kind}`;
}

function populateFilterSelect(element, values, defaultLabel) {
  if (!element) {
    return;
  }
  const currentValue = element.value;
  element.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = defaultLabel;
  element.appendChild(defaultOption);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    element.appendChild(option);
  });
  if ([...values, ""].includes(currentValue)) {
    element.value = currentValue;
  }
}

function applyFilters(tableData, options) {
  const rows = tableData.rows || [];
  const search = (options.search || "").trim().toLowerCase();
  const broker = options.broker || "";
  const currency = options.currency || "";
  return rows.filter((row) => {
    if (broker && String(row.broker || "") !== broker) {
      return false;
    }
    const rowCurrency = String(row.currency || row.price_currency || "");
    if (currency && rowCurrency !== currency) {
      return false;
    }
    if (!search) {
      return true;
    }
    return Object.values(row).some((value) => String(value ?? "").toLowerCase().includes(search));
  });
}

function formatPercentage(value) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return "-";
  }
  return `${(numberValue * 100).toFixed(2)}%`;
}

function formatPerformanceMetric(performance, key) {
  if (performance[key] !== null && performance[key] !== undefined) {
    return formatPercentage(performance[key]);
  }

  const byCurrency = performance.by_currency || {};
  const currencyEntries = Object.entries(byCurrency).filter(
    ([, metrics]) => metrics[key] !== null && metrics[key] !== undefined
  );
  if (!currencyEntries.length) {
    return "-";
  }

  return currencyEntries
    .map(([currency, metrics]) => `${currency}: ${formatPercentage(metrics[key])}`)
    .join("\n");
}

function renderPerformanceMetrics(performance = {}) {
  document.querySelector("#annualized-irr").textContent = formatPerformanceMetric(
    performance,
    "annualized_irr"
  );
  document.querySelector("#simple-return").textContent = formatPerformanceMetric(
    performance,
    "simple_return"
  );
  document.querySelector("#time-weighted-return").textContent = formatPerformanceMetric(
    performance,
    "time_weighted_return"
  );
  document.querySelector("#cagr").textContent = formatPerformanceMetric(
    performance,
    "cagr"
  );

  const assumptions = performance.assumptions || [];
  const assumptionPanel = document.querySelector("#performance-assumptions");
  assumptionPanel.innerHTML = "";
  if (!assumptions.length) {
    assumptionPanel.textContent =
      "Assumptions: none. IRR and TWR use the reported transaction history.";
    return;
  }

  const heading = document.createElement("span");
  heading.textContent = "Assumptions:";
  const list = document.createElement("ol");
  assumptions.forEach((assumption) => {
    const item = document.createElement("li");
    item.textContent = assumption;
    list.appendChild(item);
  });

  assumptionPanel.append(heading, list);
}

function getHoldingSortValue(row, column) {
  if (
    column === "annualized_irr"
    || column === "cagr"
    || column === "simple_return"
    || column === "time_weighted_return"
  ) {
    const metricValue = Number(row[column]);
    return Number.isFinite(metricValue) ? metricValue : Number.NEGATIVE_INFINITY;
  }
  return String(row[column] || "").toUpperCase();
}

function holdingPerformanceColumns() {
  return [
    { key: "stock_code", label: "Stock Code" },
    { key: "stock_name", label: "Stock Name" },
    { key: "currency", label: "Currency" },
    { key: "annualized_irr", label: "Annualized IRR" },
    { key: "simple_return", label: "Simple Return" },
    { key: "time_weighted_return", label: "Time-Weighted Return" },
    { key: "cagr", label: "CAGR" },
    { key: "assumption_note", label: "Assumptions" },
  ];
}

function renderHoldingPerformanceTable(rows = []) {
  const container = document.querySelector("#holding-performance-table");
  const caption = document.querySelector("#holding-performance-caption");
  container.innerHTML = "";
  caption.textContent = "";
  if (!rows.length) {
    container.textContent = "No holdings to display.";
    container.className = "table-wrap muted";
    return;
  }

  container.className = "table-wrap";
  const columns = holdingPerformanceColumns();
  const sortedRows = [...rows].sort((left, right) => {
    const leftValue = getHoldingSortValue(left, holdingPerformanceSort.column);
    const rightValue = getHoldingSortValue(right, holdingPerformanceSort.column);
    if (leftValue < rightValue) {
      return holdingPerformanceSort.direction === "asc" ? -1 : 1;
    }
    if (leftValue > rightValue) {
      return holdingPerformanceSort.direction === "asc" ? 1 : -1;
    }
    return 0;
  });

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  const headRow = document.createElement("tr");
  columns.forEach((column) => {
    const heading = document.createElement("th");
    heading.classList.add("sortable-header");
    heading.setAttribute("scope", "col");
    heading.setAttribute("tabindex", "0");
    const isCurrentSort = holdingPerformanceSort.column === column.key;
    const sortSuffix = isCurrentSort ? (holdingPerformanceSort.direction === "asc" ? " \u2191" : " \u2193") : "";
    heading.setAttribute(
      "aria-sort",
      isCurrentSort ? (holdingPerformanceSort.direction === "asc" ? "ascending" : "descending") : "none"
    );
    heading.textContent = `${column.label}${sortSuffix}`;
    const sortColumn = () => {
      if (holdingPerformanceSort.column === column.key) {
        holdingPerformanceSort.direction = holdingPerformanceSort.direction === "asc" ? "desc" : "asc";
      } else {
        holdingPerformanceSort.column = column.key;
        holdingPerformanceSort.direction = column.key === "stock_code" || column.key === "stock_name" ? "asc" : "desc";
      }
      renderHoldingPerformanceTable(rows);
    };
    heading.addEventListener("click", sortColumn);
    heading.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        sortColumn();
      }
    });
    headRow.appendChild(heading);
  });
  thead.appendChild(headRow);

  sortedRows.forEach((row) => {
    const bodyRow = document.createElement("tr");
    columns.forEach((column) => {
      const cell = document.createElement("td");
      if (
        column.key === "annualized_irr"
        || column.key === "cagr"
        || column.key === "simple_return"
        || column.key === "time_weighted_return"
      ) {
        cell.className = "center-cell";
        const metricValue = Number(row[column.key]);
        if (Number.isFinite(metricValue)) {
          cell.classList.add(metricValue >= 0 ? "return-positive" : "return-negative");
        }
        cell.textContent = formatPercentage(row[column.key]);
      } else {
        cell.textContent = row[column.key] || "-";
      }
      bodyRow.appendChild(cell);
    });
    tbody.appendChild(bodyRow);
  });

  table.append(thead, tbody);
  container.appendChild(table);
  caption.textContent = `Showing ${rows.length} holding(s)`;
}

function outputUrl(file, cacheKey = "") {
  const query = cacheKey ? `?v=${encodeURIComponent(cacheKey)}` : "";
  return `/outputs/${encodeURIComponent(file)}${query}`;
}

function displayName(value) {
  return String(value).split("_").join(" ");
}

function chartSortValue(chart) {
  const chartName = String(chart).toLowerCase();
  if (chartName.includes("investment_positions_by_month")) {
    return 1;
  }
  if (chartName.includes("transactions_by_month")) {
    return 2;
  }
  if (chartName.includes("sector_distribution")) {
    return 3;
  }
  if (chartName.includes("geography_distribution")) {
    return 4;
  }
  if (chartName.includes("country_exposure_pie_sgd")) {
    return 5;
  }
  if (chartName.includes("country_exposure_pie_usd")) {
    return 6;
  }
  return 99;
}

function chartGroupName(chart) {
  const chartName = String(chart).toLowerCase();
  if (chartName.includes("investment_positions_by_month")) {
    return "Portfolio Trend";
  }
  if (chartName.includes("transactions_by_month")) {
    return "Transactions Trend";
  }
  if (chartName.includes("sector_distribution") || chartName.includes("geography_distribution")) {
    return "Allocation";
  }
  if (chartName.includes("country_exposure_pie")) {
    return "Country Exposure";
  }
  return "Other";
}

function chartDisplayName(chart) {
  const chartName = String(chart).toLowerCase();
  const chartFile = String(chart);
  const extractCurrency = (prefix, extension) => {
    const escapedPrefix = prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const escapedExt = extension.replace(".", "\\.");
    const match = chartFile.match(new RegExp(`^${escapedPrefix}_([A-Za-z0-9]+)_\\d{4}-\\d{2}-\\d{2}\\.${escapedExt}$`, "i"));
    return match ? match[1].toUpperCase() : "";
  };
  if (chartName.includes("investment_positions_by_month")) {
    return "Portfolio Value by Month";
  }
  if (chartName.includes("transactions_by_month")) {
    return "Transactions by Month";
  }
  if (chartName.includes("sector_distribution")) {
    const currency = extractCurrency("seaborn_sector_distribution", "png")
      || extractCurrency("plotly_sector_distribution", "html");
    return currency ? `Sector Distribution (${currency})` : "Sector Distribution";
  }
  if (chartName.includes("geography_distribution")) {
    const currency = extractCurrency("seaborn_geography_distribution", "png")
      || extractCurrency("plotly_geography_distribution", "html");
    return currency ? `Geography Distribution (${currency})` : "Geography Distribution";
  }
  if (chartName.includes("country_exposure_pie_sgd")) {
    return "Country Exposure (SGD)";
  }
  if (chartName.includes("country_exposure_pie_usd")) {
    return "Country Exposure (USD)";
  }
  return displayName(chart);
}

function formatDisplayValue(tableId, column, value) {
  const decimalColumnsByTable = {
    "transactions-table": new Set(["transaction_price", "units", "transaction_amount"]),
    "positions-table": new Set([
      "quantity",
      "average_cost_price",
      "market_value",
      "total_cost",
      "unrealized_pl",
    ]),
  };
  const decimalColumns = decimalColumnsByTable[tableId];
  if (!decimalColumns || !decimalColumns.has(column) || value === "") {
    return value;
  }

  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return value;
  }

  return numberValue.toFixed(2);
}

function isNumericColumn(tableId, column) {
  const numericColumnsByTable = {
    "transactions-table": new Set(["transaction_price", "units", "transaction_amount"]),
    "positions-table": new Set([
      "quantity",
      "average_cost_price",
      "last_done_price",
      "market_value",
      "total_cost",
      "unrealized_pl",
    ]),
  };
  return numericColumnsByTable[tableId]?.has(column) || false;
}

function setStatus(message) {
  statusText.textContent = message;
}

function setButtonsDisabled(disabled) {
  runButton.disabled = disabled;
  uploadSubmitButton.disabled = disabled;
  deleteBrokerFilesButton.disabled = disabled;
  deleteOutputFilesButton.disabled = disabled;
  clearScreenButton.disabled = disabled;
  showSeabornChartsButton.disabled = disabled;
  showPlotlyChartsButton.disabled = disabled;
}

function confirmAction(message) {
  return window.confirm(message);
}

function formatUploadResult(data) {
  const poemsCount = data.saved_files.poems_files.length;
  const ibCount = data.saved_files.interactive_brokers_files.length;
  const rejectedCount = data.rejected_files.length;
  const parts = [`Uploaded ${poemsCount} POEMS file(s) and ${ibCount} Interactive Brokers file(s).`];
  if (rejectedCount) {
    parts.push(`${rejectedCount} file(s) were rejected.`);
  }
  return parts.join(" ");
}

function renderFileList(elementId, files) {
  const list = document.querySelector(elementId);
  list.innerHTML = "";
  if (!files.length) {
    const item = document.createElement("li");
    item.textContent = "No files found";
    item.className = "muted";
    list.appendChild(item);
    return;
  }

  files.forEach((file) => {
    const item = document.createElement("li");
    item.textContent = file;
    list.appendChild(item);
  });
}

function renderLinks(elementId, files) {
  const container = document.querySelector(elementId);
  container.innerHTML = "";
  if (!files.length) {
    container.textContent = "No output files were generated.";
    container.className = "link-row muted";
    return;
  }

  container.className = "link-row";
  files.forEach((file) => {
    const link = document.createElement("a");
    link.href = outputUrl(file);
    link.textContent = file;
    link.target = "_blank";
    link.rel = "noreferrer";
    container.appendChild(link);
  });
}

function renderCharts(charts, cacheKey) {
  const grid = document.querySelector("#chart-grid");
  grid.innerHTML = "";
  if (!charts.length) {
    grid.textContent = "No chart images were generated.";
    grid.className = "chart-grid muted";
    return;
  }

  grid.className = "chart-grid";
  let previousGroup = "";
  [...charts].sort((left, right) => chartSortValue(left) - chartSortValue(right)).forEach((chart) => {
    const group = chartGroupName(chart);
    if (group !== previousGroup) {
      const groupHeading = document.createElement("div");
      groupHeading.className = "chart-group-title";
      groupHeading.textContent = group;
      grid.appendChild(groupHeading);
      previousGroup = group;
    }
    const figure = document.createElement("figure");
    if (group === "Portfolio Trend" || group === "Transactions Trend") {
      figure.classList.add("chart-wide");
    }
    const caption = document.createElement("figcaption");
    if (chart.toLowerCase().endsWith(".html")) {
      const frame = document.createElement("iframe");
      frame.src = outputUrl(chart, cacheKey);
      frame.title = chartDisplayName(chart);
      frame.loading = "lazy";
      frame.onerror = () => {
        figure.classList.add("chart-error");
        caption.textContent = `${chartDisplayName(chart)} could not be loaded`;
      };
      figure.appendChild(frame);
    } else {
      const image = document.createElement("img");
      image.src = outputUrl(chart, cacheKey);
      image.alt = chartDisplayName(chart);
      image.onerror = () => {
        figure.classList.add("chart-error");
        caption.textContent = `${chartDisplayName(chart)} could not be loaded`;
      };
      figure.appendChild(image);
    }
    caption.textContent = chartDisplayName(chart);
    const actions = document.createElement("div");
    actions.className = "chart-actions";
    const expandButton = document.createElement("button");
    expandButton.type = "button";
    expandButton.textContent = "Expand";
    expandButton.addEventListener("click", () => {
      const expanded = figure.classList.toggle("chart-expanded");
      expandButton.textContent = expanded ? "Collapse" : "Expand";
    });
    const openLink = document.createElement("a");
    openLink.href = outputUrl(chart, cacheKey);
    openLink.target = "_blank";
    openLink.rel = "noreferrer";
    openLink.textContent = "Open";
    const downloadLink = document.createElement("a");
    downloadLink.href = outputUrl(chart, cacheKey);
    downloadLink.download = chart;
    downloadLink.textContent = "Download";
    actions.append(expandButton, openLink, downloadLink);
    figure.appendChild(actions);
    figure.appendChild(caption);
    grid.appendChild(figure);
  });
}

function setChartMode(mode) {
  currentChartMode = mode;
  try {
    window.localStorage.setItem(CHART_MODE_STORAGE_KEY, mode);
  } catch (_error) {
    // Ignore persistence failure and continue.
  }
  showSeabornChartsButton.classList.toggle("active", mode === "seaborn");
  showPlotlyChartsButton.classList.toggle("active", mode === "plotly");
  renderCharts(currentChartSets[mode] || [], currentChartCacheKey);
}

function renderTable(elementId, tableData) {
  const container = document.querySelector(elementId);
  container.innerHTML = "";
  if (!tableData.rows.length) {
    container.textContent = "No rows to display.";
    container.className = "table-wrap muted";
    return;
  }

  container.className = "table-wrap";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  const headRow = document.createElement("tr");

  const tableId = container.id;
  const isPositionsTable = tableId === "positions-table";
  const sortedRows = isPositionsTable
    ? [...(tableData.rows || [])].sort((left, right) => {
      const column = positionsSort.column;
      const leftRaw = left[column];
      const rightRaw = right[column];
      const leftNumber = Number(leftRaw);
      const rightNumber = Number(rightRaw);
      let comparison = 0;
      if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
        comparison = leftNumber === rightNumber ? 0 : (leftNumber < rightNumber ? -1 : 1);
      } else {
        const leftText = String(leftRaw ?? "").toUpperCase();
        const rightText = String(rightRaw ?? "").toUpperCase();
        comparison = leftText.localeCompare(rightText);
      }
      return positionsSort.direction === "asc" ? comparison : -comparison;
    })
    : (tableData.rows || []);

  tableData.columns.forEach((column) => {
    const heading = document.createElement("th");
    if (isPositionsTable) {
      heading.classList.add("sortable-header");
      heading.setAttribute("scope", "col");
      heading.setAttribute("tabindex", "0");
      const isCurrentSort = positionsSort.column === column;
      const sortSuffix = isCurrentSort ? (positionsSort.direction === "asc" ? " \u2191" : " \u2193") : "";
      heading.setAttribute(
        "aria-sort",
        isCurrentSort ? (positionsSort.direction === "asc" ? "ascending" : "descending") : "none"
      );
      heading.textContent = `${displayName(column)}${sortSuffix}`;
      const applySort = () => {
        if (positionsSort.column === column) {
          positionsSort.direction = positionsSort.direction === "asc" ? "desc" : "asc";
        } else {
          positionsSort.column = column;
          positionsSort.direction = isNumericColumn(tableId, column) ? "desc" : "asc";
        }
        renderFilteredTables();
      };
      heading.addEventListener("click", applySort);
      heading.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          applySort();
        }
      });
    } else {
      heading.textContent = displayName(column);
    }
    headRow.appendChild(heading);
  });
  thead.appendChild(headRow);

  sortedRows.forEach((row) => {
    const bodyRow = document.createElement("tr");
    tableData.columns.forEach((column) => {
      const cell = document.createElement("td");
      if (isNumericColumn(container.id, column)) {
        cell.className = "numeric-cell";
      }
      if (container.id === "positions-table" && column === "unrealized_pl") {
        const numberValue = Number(row[column]);
        if (Number.isFinite(numberValue)) {
          cell.classList.add(numberValue >= 0 ? "return-positive" : "return-negative");
        }
      }
      cell.textContent = formatDisplayValue(
        container.id,
        column,
        row[column]
      );
      bodyRow.appendChild(cell);
    });
    tbody.appendChild(bodyRow);
  });

  table.append(thead, tbody);
  container.appendChild(table);
}

function renderFilteredTables() {
  const filteredTransactions = applyFilters(transactionsData, {
    search: transactionsSearchInput?.value || "",
    broker: transactionsBrokerFilter?.value || "",
    currency: transactionsCurrencyFilter?.value || "",
  });
  const filteredPositions = applyFilters(positionsData, {
    search: positionsSearchInput?.value || "",
    broker: positionsBrokerFilter?.value || "",
    currency: positionsCurrencyFilter?.value || "",
  });
  renderTable("#transactions-table", {
    columns: transactionsData.columns || [],
    rows: filteredTransactions,
    total_rows: filteredTransactions.length,
  });
  renderTable("#positions-table", {
    columns: positionsData.columns || [],
    rows: filteredPositions,
    total_rows: filteredPositions.length,
  });
  document.querySelector("#transaction-caption").textContent =
    `Showing ${filteredTransactions.length} of ${transactionsData.total_rows || 0} row(s)`;
  document.querySelector("#position-caption").textContent =
    `Showing ${filteredPositions.length} of ${positionsData.total_rows || 0} row(s)`;
}

function clearScreen() {
  document.querySelector("#poems-count").textContent = "0";
  document.querySelector("#ib-count").textContent = "0";
  document.querySelector("#transaction-count").textContent = "0";
  document.querySelector("#position-count").textContent = "0";
  renderPerformanceMetrics();

  renderFileList("#poems-files", []);
  renderFileList("#ib-files", []);
  currentChartSets = {
    seaborn: [],
    plotly: [],
  };
  currentChartCacheKey = Date.now().toString();
  renderCharts([], Date.now().toString());
  renderLinks("#csv-links", []);
  transactionsData = { columns: [], rows: [], total_rows: 0 };
  positionsData = { columns: [], rows: [], total_rows: 0 };
  renderTable("#transactions-table", { columns: [], rows: [], total_rows: 0 });
  renderTable("#positions-table", { columns: [], rows: [], total_rows: 0 });
  renderHoldingPerformanceTable([]);

  document.querySelector("#transaction-caption").textContent = "";
  document.querySelector("#position-caption").textContent = "";
  setConsoleOutput(DEFAULT_CONSOLE_MESSAGE);
  setStatus("Ready");
  setNotice("Cleared all on-screen data.", "info");
}

async function deleteFiles(endpoint, runningStatus, successMessage, afterDelete = null) {
  setButtonsDisabled(true);
  setStatus(runningStatus);
  setNotice(runningStatus, "info");

  try {
    const response = await fetch(endpoint, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The delete request could not complete.");
    }

    const failedCount = data.failed_count || 0;
    const statusMessage = `${successMessage} Deleted ${data.deleted_count} file(s).`;
    if (afterDelete) {
      afterDelete(data);
    }
    if (failedCount) {
      setConsoleOutput(
        `${statusMessage} ${failedCount} file(s) could not be deleted because they are still in use. Close the file or restart the app, then try again.`
      );
      setStatus("Partial");
      setNotice("Action partially completed. Some files are still in use.", "warn");
    } else {
      setConsoleOutput(statusMessage);
      setStatus(`${successMessage}`);
      setNotice(statusMessage, "success");
    }
  } catch (error) {
    setStatus("Failed");
    setConsoleOutput(error.message);
    setNotice(error.message, "error");
  } finally {
    setButtonsDisabled(false);
  }
}

async function runReport() {
  setButtonsDisabled(true);
  setStatus("Generating report from broker files...");
  setConsoleOutput("Running report...");
  setNotice("Running report...", "info");

  try {
    const response = await fetch("/api/run-report");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The report could not complete.");
    }

    document.querySelector("#poems-count").textContent = data.poems_files.length;
    document.querySelector("#ib-count").textContent = data.interactive_brokers_files.length;
    document.querySelector("#transaction-count").textContent = data.transactions.total_rows;
    document.querySelector("#position-count").textContent = data.positions.total_rows;
    renderPerformanceMetrics(data.performance || {});
    renderHoldingPerformanceTable((data.performance || {}).by_holding || []);

    renderFileList("#poems-files", data.poems_files);
    renderFileList("#ib-files", data.interactive_brokers_files);
    currentChartSets = data.chart_sets || {
      seaborn: data.charts || [],
      plotly: [],
    };
    currentChartCacheKey = `${data.generated_on || "chart"}-${Date.now()}`;
    renderCharts(currentChartSets[currentChartMode] || [], currentChartCacheKey);
    renderLinks("#csv-links", data.csv_files);
    transactionsData = data.transactions;
    positionsData = data.positions;
    populateFilterSelect(
      transactionsBrokerFilter,
      [...new Set((transactionsData.rows || []).map((row) => String(row.broker || "")).filter(Boolean))].sort(),
      "All brokers"
    );
    populateFilterSelect(
      transactionsCurrencyFilter,
      [...new Set((transactionsData.rows || []).map((row) => String(row.price_currency || row.currency || "")).filter(Boolean))].sort(),
      "All currencies"
    );
    populateFilterSelect(
      positionsBrokerFilter,
      [...new Set((positionsData.rows || []).map((row) => String(row.broker || "")).filter(Boolean))].sort(),
      "All brokers"
    );
    populateFilterSelect(
      positionsCurrencyFilter,
      [...new Set((positionsData.rows || []).map((row) => String(row.currency || "")).filter(Boolean))].sort(),
      "All currencies"
    );
    renderFilteredTables();
    setConsoleOutput(data.console_output || "No console output was produced.");
    setStatus(`Report ready: ${data.transactions.total_rows} transactions, ${data.positions.total_rows} positions.`);
    setNotice("Report completed successfully.", "success");
  } catch (error) {
    setStatus("Failed");
    setConsoleOutput(error.message);
    setNotice(error.message, "error");
  } finally {
    setButtonsDisabled(false);
  }
}

async function uploadFiles(event) {
  event.preventDefault();
  const formData = new FormData(uploadForm);
  const hasFiles = Array.from(formData.values()).some((value) => value instanceof File && value.name);
  if (!hasFiles) {
    uploadMessage.textContent = "Choose at least one POEMS workbook or Interactive Brokers CSV.";
    return;
  }

  setButtonsDisabled(true);
  setStatus("Uploading broker files...");
  uploadMessage.textContent = "Uploading files...";
  setNotice("Uploading files...", "info");

  try {
    const response = await fetch("/api/upload-files", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The upload could not complete.");
    }

    uploadMessage.textContent = formatUploadResult(data);
    setNotice(uploadMessage.textContent, "success");
    uploadForm.reset();
    await runReport();
  } catch (error) {
    setStatus("Upload failed");
    uploadMessage.textContent = error.message;
    setNotice(error.message, "error");
  } finally {
    setButtonsDisabled(false);
  }
}

showUploadButton.addEventListener("click", () => {
  uploadPanel.hidden = !uploadPanel.hidden;
});
adminModeToggleButton?.addEventListener("click", () => {
  if (isAdminModeEnabled) {
    setAdminModeUiState(false);
    adminModeBadge.hidden = true;
    setNotice("Admin mode disabled.", "info");
    return;
  }

  const unlockCode = window.prompt("Enter ADMIN to log in to Admin Mode:");
  if (unlockCode !== ADMIN_MODE_CODE) {
    window.alert("Invalid admin code.");
    return;
  }

  setAdminModeUiState(true);
  if (!adminModePanel.hidden) {
    adminModePanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  setNotice("Admin mode enabled. Destructive actions are now available.", "warn");
});
runButton.addEventListener("click", runReport);
showSeabornChartsButton.addEventListener("click", () => {
  setChartMode("seaborn");
});
showPlotlyChartsButton.addEventListener("click", () => {
  setChartMode("plotly");
});
deleteBrokerFilesButton.addEventListener("click", () => {
  if (!confirmAction("Delete all files in the POEMS and Interactive Brokers folders?")) {
    return;
  }

  deleteFiles(
    "/api/delete-broker-files",
    "Deleting broker files",
    "Deleted POEMS and Interactive Brokers files.",
    () => {
      document.querySelector("#poems-count").textContent = "0";
      document.querySelector("#ib-count").textContent = "0";
      renderFileList("#poems-files", []);
      renderFileList("#ib-files", []);
    }
  );
});
deleteOutputFilesButton.addEventListener("click", () => {
  if (!confirmAction("Delete all files in the Output folder?")) {
    return;
  }

  deleteFiles(
    "/api/delete-output-files",
    "Deleting output files",
    "Deleted Output folder files.",
    (data) => {
      const failedFiles = data.result?.failed_files || [];
      const remainingFiles = failedFiles.map((failure) => failure.file);
      renderLinks(
        "#csv-links",
        remainingFiles.filter((file) => file.toLowerCase().endsWith(".csv"))
      );
    }
  );
});
clearScreenButton.addEventListener("click", () => {
  if (!confirmAction("Clear all data and visualizations from the screen?")) {
    return;
  }

  clearScreen();
});
transactionsSearchInput?.addEventListener("input", renderFilteredTables);
positionsSearchInput?.addEventListener("input", renderFilteredTables);
transactionsBrokerFilter?.addEventListener("change", renderFilteredTables);
transactionsCurrencyFilter?.addEventListener("change", renderFilteredTables);
positionsBrokerFilter?.addEventListener("change", renderFilteredTables);
positionsCurrencyFilter?.addEventListener("change", renderFilteredTables);
function applyRowDensity(value) {
  const compact = value === "compact";
  document.querySelector("#transactions-table").classList.toggle("compact-rows", compact);
  document.querySelector("#positions-table").classList.toggle("compact-rows", compact);
  document.querySelector("#holding-performance-table").classList.toggle("compact-rows", compact);
}

rowDensitySelect?.addEventListener("change", () => {
  const value = rowDensitySelect.value;
  if (positionsRowDensitySelect) {
    positionsRowDensitySelect.value = value;
  }
  applyRowDensity(value);
});

positionsRowDensitySelect?.addEventListener("change", () => {
  const value = positionsRowDensitySelect.value;
  if (rowDensitySelect) {
    rowDensitySelect.value = value;
  }
  applyRowDensity(value);
});
uploadForm.addEventListener("submit", uploadFiles);
document.addEventListener("DOMContentLoaded", () => {
  try {
    const savedChartMode = window.localStorage.getItem(CHART_MODE_STORAGE_KEY);
    if (savedChartMode === "seaborn" || savedChartMode === "plotly") {
      currentChartMode = savedChartMode;
      showSeabornChartsButton.classList.toggle("active", savedChartMode === "seaborn");
      showPlotlyChartsButton.classList.toggle("active", savedChartMode === "plotly");
    }
  } catch (_error) {
    // Ignore localStorage errors and keep defaults.
  }
  setAdminModeUiState(false);
  runReport();
});
