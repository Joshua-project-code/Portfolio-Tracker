const runAllTestsButton = document.querySelector("#run-all-tests");
const testSummary = document.querySelector("#test-summary");
const testingStatus = document.querySelector("#testing-status");
const testCaseList = document.querySelector("#test-case-list");

let testCases = [];
const testResults = new Map();

function setTestingStatus(message) {
  testingStatus.textContent = message;
}

function updateSummary() {
  const passedCount = Array.from(testResults.values()).filter(
    (status) => status === "passed"
  ).length;
  testSummary.textContent = `${passedCount} passed out of a total of ${testCases.length} tests`;
}

function statusLabel(status) {
  if (status === "passed") {
    return "passed";
  }
  if (status === "failed") {
    return "failed";
  }
  if (status === "running") {
    return "running";
  }
  return "not run";
}

function setRowStatus(testName, status) {
  testResults.set(testName, status);
  const row = document.querySelector(`[data-test-name="${testName}"]`);
  if (!row) {
    updateSummary();
    return;
  }

  const result = row.querySelector(".test-result");
  result.className = `test-result ${status}`;
  result.textContent = statusLabel(status);
  updateSummary();
}

function setButtonsDisabled(disabled) {
  runAllTestsButton.disabled = disabled;
  document.querySelectorAll(".run-test").forEach((button) => {
    button.disabled = disabled;
  });
}

function renderTestCases() {
  testCaseList.innerHTML = "";
  testResults.clear();

  if (!testCases.length) {
    testCaseList.textContent = "No test cases found.";
    testCaseList.className = "test-case-list muted";
    updateSummary();
    return;
  }

  testCaseList.className = "test-case-list";
  testCases.forEach((testCase) => {
    testResults.set(testCase.name, "not-run");

    const row = document.createElement("article");
    row.className = "test-case-row";
    row.dataset.testName = testCase.name;

    const details = document.createElement("div");
    details.className = "test-case-details";

    const title = document.createElement("h3");
    title.textContent = `${testCase.id} ${testCase.name}`;

    const description = document.createElement("p");
    description.textContent = testCase.description;

    const expected = document.createElement("p");
    expected.className = "test-expected";
    expected.textContent = `Expected: ${testCase.expected_output}`;

    const actions = document.createElement("div");
    actions.className = "test-case-actions";

    const result = document.createElement("span");
    result.className = "test-result not-run";
    result.textContent = "not run";

    const button = document.createElement("button");
    button.className = "run-test";
    button.type = "button";
    button.textContent = "Run Test";
    button.addEventListener("click", () => runSingleTest(testCase.name));

    details.append(title, description, expected);
    actions.append(result, button);
    row.append(details, actions);
    testCaseList.appendChild(row);
  });

  updateSummary();
}

async function loadTestCases() {
  setTestingStatus("Loading");
  try {
    const response = await fetch("/api/tests");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The test catalogue could not be loaded.");
    }

    testCases = data.tests;
    renderTestCases();
    setTestingStatus("Ready");
  } catch (error) {
    setTestingStatus("Failed");
    testCaseList.textContent = error.message;
    testCaseList.className = "test-case-list muted";
  }
}

async function runTestRequest(testName = null) {
  const body = testName ? { test_name: testName } : {};
  const response = await fetch("/api/tests/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "The test run could not complete.");
  }
  return data;
}

async function runSingleTest(testName) {
  setButtonsDisabled(true);
  setTestingStatus("Running");
  setRowStatus(testName, "running");

  try {
    const data = await runTestRequest(testName);
    const status = data.results[testName] || (data.ok ? "passed" : "failed");
    setRowStatus(testName, status);
    setTestingStatus("Ready");
  } catch (error) {
    setRowStatus(testName, "failed");
    setTestingStatus(error.message);
  } finally {
    setButtonsDisabled(false);
  }
}

async function runAllTests() {
  setButtonsDisabled(true);
  setTestingStatus("Running");
  testCases.forEach((testCase) => setRowStatus(testCase.name, "running"));

  try {
    const data = await runTestRequest();
    testCases.forEach((testCase) => {
      setRowStatus(testCase.name, data.results[testCase.name] || "failed");
    });
    setTestingStatus(data.ok ? "Complete" : "Failed");
  } catch (error) {
    testCases.forEach((testCase) => setRowStatus(testCase.name, "failed"));
    setTestingStatus(error.message);
  } finally {
    setButtonsDisabled(false);
  }
}

runAllTestsButton.addEventListener("click", runAllTests);
document.addEventListener("DOMContentLoaded", loadTestCases);
