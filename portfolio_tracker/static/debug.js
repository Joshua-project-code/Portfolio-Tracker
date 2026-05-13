const CONSOLE_OUTPUT_STORAGE_KEY = "portfolio_tracker_console_output";
const DEFAULT_CONSOLE_MESSAGE = "Run the report to display parser output here.";
const consoleOutput = document.querySelector("#console-output");
const refreshButton = document.querySelector("#refresh-console");

function loadConsoleOutput() {
  let message = DEFAULT_CONSOLE_MESSAGE;
  try {
    message = window.localStorage.getItem(CONSOLE_OUTPUT_STORAGE_KEY) || DEFAULT_CONSOLE_MESSAGE;
  } catch (_error) {
    message = DEFAULT_CONSOLE_MESSAGE;
  }
  consoleOutput.textContent = message;
}

refreshButton?.addEventListener("click", loadConsoleOutput);
window.addEventListener("storage", (event) => {
  if (event.key === CONSOLE_OUTPUT_STORAGE_KEY) {
    loadConsoleOutput();
  }
});
document.addEventListener("DOMContentLoaded", loadConsoleOutput);
