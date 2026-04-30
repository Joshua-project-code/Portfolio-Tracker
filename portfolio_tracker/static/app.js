const runButton = document.querySelector("#run-report");
const showUploadButton = document.querySelector("#show-upload");
const deleteBrokerFilesButton = document.querySelector("#delete-broker-files");
const deleteOutputFilesButton = document.querySelector("#delete-output-files");
const clearScreenButton = document.querySelector("#clear-screen");
const uploadPanel = document.querySelector("#upload-panel");
const uploadForm = document.querySelector("#upload-form");
const uploadSubmitButton = document.querySelector("#upload-submit");
const uploadMessage = document.querySelector("#upload-message");
const statusText = document.querySelector("#status-text");

function outputUrl(file, cacheKey = "") {
  const query = cacheKey ? `?v=${encodeURIComponent(cacheKey)}` : "";
  return `/outputs/${encodeURIComponent(file)}${query}`;
}

function displayName(value) {
  return String(value).split("_").join(" ");
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
  charts.forEach((chart) => {
    const figure = document.createElement("figure");
    const image = document.createElement("img");
    const caption = document.createElement("figcaption");
    image.src = outputUrl(chart, cacheKey);
    image.alt = displayName(chart);
    image.onerror = () => {
      figure.classList.add("chart-error");
      caption.textContent = `${chart} could not be loaded`;
    };
    caption.textContent = chart;
    figure.append(image, caption);
    grid.appendChild(figure);
  });
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

  tableData.columns.forEach((column) => {
    const heading = document.createElement("th");
    heading.textContent = displayName(column);
    headRow.appendChild(heading);
  });
  thead.appendChild(headRow);

  tableData.rows.forEach((row) => {
    const bodyRow = document.createElement("tr");
    tableData.columns.forEach((column) => {
      const cell = document.createElement("td");
      if (isNumericColumn(container.id, column)) {
        cell.className = "numeric-cell";
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

function clearScreen() {
  document.querySelector("#poems-count").textContent = "0";
  document.querySelector("#ib-count").textContent = "0";
  document.querySelector("#transaction-count").textContent = "0";
  document.querySelector("#position-count").textContent = "0";

  renderFileList("#poems-files", []);
  renderFileList("#ib-files", []);
  renderCharts([], Date.now().toString());
  renderLinks("#csv-links", []);
  renderTable("#transactions-table", { columns: [], rows: [], total_rows: 0 });
  renderTable("#positions-table", { columns: [], rows: [], total_rows: 0 });

  document.querySelector("#transaction-caption").textContent = "";
  document.querySelector("#position-caption").textContent = "";
  document.querySelector("#console-output").textContent =
    "Run the report to display parser output here.";
  setStatus("Ready");
}

async function deleteFiles(endpoint, runningStatus, successMessage, afterDelete = null) {
  setButtonsDisabled(true);
  setStatus(runningStatus);

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
      document.querySelector("#console-output").textContent =
        `${statusMessage} ${failedCount} file(s) could not be deleted because they are still in use. Close the file or restart the app, then try again.`;
      setStatus("Partial");
    } else {
      document.querySelector("#console-output").textContent = statusMessage;
      setStatus("Complete");
    }
  } catch (error) {
    setStatus("Failed");
    document.querySelector("#console-output").textContent = error.message;
  } finally {
    setButtonsDisabled(false);
  }
}

async function runReport() {
  setButtonsDisabled(true);
  setStatus("Running");
  document.querySelector("#console-output").textContent = "Running report...";

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

    renderFileList("#poems-files", data.poems_files);
    renderFileList("#ib-files", data.interactive_brokers_files);
    renderCharts(data.charts, data.generated_on || Date.now().toString());
    renderLinks("#csv-links", data.csv_files);
    renderTable("#transactions-table", data.transactions);
    renderTable("#positions-table", data.positions);

    document.querySelector("#transaction-caption").textContent =
      `Showing ${data.transactions.rows.length} row(s)`;
    document.querySelector("#position-caption").textContent =
      `Showing ${data.positions.rows.length} row(s)`;
    document.querySelector("#console-output").textContent =
      data.console_output || "No console output was produced.";
    setStatus("Complete");
  } catch (error) {
    setStatus("Failed");
    document.querySelector("#console-output").textContent = error.message;
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
  setStatus("Uploading");
  uploadMessage.textContent = "Uploading files...";

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
    uploadForm.reset();
    await runReport();
  } catch (error) {
    setStatus("Upload failed");
    uploadMessage.textContent = error.message;
  } finally {
    setButtonsDisabled(false);
  }
}

showUploadButton.addEventListener("click", () => {
  uploadPanel.hidden = !uploadPanel.hidden;
});
runButton.addEventListener("click", runReport);
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
uploadForm.addEventListener("submit", uploadFiles);
document.addEventListener("DOMContentLoaded", runReport);
