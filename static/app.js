const runButton = document.querySelector("#run-report");
const showUploadButton = document.querySelector("#show-upload");
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

function setStatus(message) {
  statusText.textContent = message;
}

function setButtonsDisabled(disabled) {
  runButton.disabled = disabled;
  uploadSubmitButton.disabled = disabled;
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
      cell.textContent = row[column];
      bodyRow.appendChild(cell);
    });
    tbody.appendChild(bodyRow);
  });

  table.append(thead, tbody);
  container.appendChild(table);
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
      `Top ${data.transactions.rows.length} of ${data.transactions.total_rows} rows`;
    document.querySelector("#position-caption").textContent =
      `Top ${data.positions.rows.length} of ${data.positions.total_rows} rows`;
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
uploadForm.addEventListener("submit", uploadFiles);
document.addEventListener("DOMContentLoaded", runReport);
