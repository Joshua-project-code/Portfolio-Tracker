const CONSOLE_OUTPUT_STORAGE_KEY = "portfolio_tracker_console_output";
const DEFAULT_CONSOLE_MESSAGE = "Run the report to display parser output here.";
const consoleOutput = document.querySelector("#console-output");
const refreshButton = document.querySelector("#refresh-console");
const refreshStatus = document.querySelector("#debug-refresh-status");
const lastRefreshed = document.querySelector("#debug-last-refreshed");
const refreshResult = document.querySelector("#debug-refresh-result");
const refreshNotice = document.querySelector("#debug-refresh-notice");
const refreshHistoryPanel = document.querySelector("#debug-refresh-history-panel");
const refreshHistory = document.querySelector("#debug-refresh-history");

const refreshEvents = [];
let previousConsoleText = null;

function timestampLabel() {
  return new Date().toLocaleString();
}

function setNotice(message, kind = "info") {
  if (!refreshNotice) {
    return;
  }
  if (!message) {
    refreshNotice.hidden = true;
    refreshNotice.textContent = "";
    refreshNotice.className = "notice-row";
    return;
  }
  refreshNotice.hidden = false;
  refreshNotice.textContent = message;
  refreshNotice.className = `notice-row ${kind}`;
}

function pushRefreshEvent(message) {
  if (!refreshHistoryPanel || !refreshHistory) {
    return;
  }
  refreshEvents.unshift(`${timestampLabel()} - ${message}`);
  while (refreshEvents.length > 3) {
    refreshEvents.pop();
  }
  refreshHistoryPanel.hidden = false;
  refreshHistory.innerHTML = "";
  refreshEvents.forEach((entry) => {
    const item = document.createElement("li");
    item.textContent = entry;
    refreshHistory.appendChild(item);
  });
}

function readConsoleOutput() {
  let message = DEFAULT_CONSOLE_MESSAGE;
  try {
    message = window.localStorage.getItem(CONSOLE_OUTPUT_STORAGE_KEY) || DEFAULT_CONSOLE_MESSAGE;
  } catch (_error) {
    message = DEFAULT_CONSOLE_MESSAGE;
  }
  return message;
}

function loadConsoleOutput(options = { announce: false }) {
  const currentText = readConsoleOutput();
  const hasChanged = previousConsoleText !== null && currentText !== previousConsoleText;
  const timestamp = timestampLabel();

  if (refreshStatus) {
    refreshStatus.textContent = "Ready";
  }
  if (lastRefreshed) {
    lastRefreshed.textContent = timestamp;
  }
  if (refreshResult) {
    refreshResult.textContent = hasChanged ? "Updated" : "No changes";
  }

  consoleOutput.textContent = currentText;
  previousConsoleText = currentText;

  if (options.announce) {
    if (hasChanged) {
      setNotice("Refreshed. New output received.", "success");
      pushRefreshEvent("Refreshed - updated");
    } else {
      setNotice("Refreshed. No new output.", "info");
      pushRefreshEvent("Refreshed - no changes");
    }
  }
}

async function refreshConsoleOutput() {
  if (refreshButton) {
    refreshButton.disabled = true;
    refreshButton.textContent = "Refreshing...";
  }
  if (refreshStatus) {
    refreshStatus.textContent = "Refreshing...";
  }

  try {
    loadConsoleOutput({ announce: true });
  } catch (error) {
    if (refreshStatus) {
      refreshStatus.textContent = "Failed";
    }
    if (refreshResult) {
      refreshResult.textContent = "Refresh failed";
    }
    setNotice(`Refresh failed: ${error.message || "Unknown error."}`, "error");
    pushRefreshEvent("Refresh failed");
  } finally {
    if (refreshButton) {
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh";
    }
  }
}

function initializeConsoleOutput() {
  const initialText = readConsoleOutput();
  previousConsoleText = initialText;
  consoleOutput.textContent = initialText;
  if (refreshStatus) {
    refreshStatus.textContent = "Ready";
  }
  if (refreshResult) {
    refreshResult.textContent = "Loaded";
  }
  if (lastRefreshed) {
    lastRefreshed.textContent = timestampLabel();
  }
  setNotice("", "info");
}

refreshButton?.addEventListener("click", refreshConsoleOutput);
window.addEventListener("storage", (event) => {
  if (event.key === CONSOLE_OUTPUT_STORAGE_KEY) {
    loadConsoleOutput({ announce: false });
  }
});
document.addEventListener("DOMContentLoaded", initializeConsoleOutput);
