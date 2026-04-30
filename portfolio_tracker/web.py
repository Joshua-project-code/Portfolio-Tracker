# This module provides the Flask web server for Portfolio Tracker. It serves
# the browser UI, runs the parser workflow on demand, and exposes generated
# Output files so users can inspect CSV and chart results from the web app.

from __future__ import annotations

import re
import gc
import os
import subprocess
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from .constants import (
    CSV_EXTENSIONS,
    DEFAULT_BROKER_ROOT_PATH,
    DEFAULT_INTERACTIVE_BROKERS_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_POEMS_PATH,
    DEFAULT_STOCK_CODE_MAPPING_PATH,
    EXCEL_EXTENSIONS,
)
from .file_helpers import ensure_folder_exists
from .parse_broker_reports import get_user_friendly_error_message
from .report_runner import run_report_with_console_output


app = Flask(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CATALOG_PATH = PROJECT_ROOT / "docs" / "testapp.md"
TESTS_PATH = PROJECT_ROOT / "tests"
STATIC_PATH = PROJECT_ROOT / "portfolio_tracker" / "static"


UPLOAD_TARGETS = {
    "poems_files": {
        "folder": DEFAULT_POEMS_PATH,
        "extensions": EXCEL_EXTENSIONS,
        "label": "POEMS",
    },
    "interactive_brokers_files": {
        "folder": DEFAULT_INTERACTIVE_BROKERS_PATH,
        "extensions": CSV_EXTENSIONS,
        "label": "Interactive Brokers",
    },
}


def get_static_version() -> int:
    """Return a cache-busting version for frontend assets."""
    asset_paths = [
        STATIC_PATH / "app.js",
        STATIC_PATH / "styles.css",
    ]
    return max(int(path.stat().st_mtime) for path in asset_paths if path.exists())


@app.get("/")
def index():
    """Render the Portfolio Tracker web app."""
    return render_template(
        "index.html",
        default_root_path=str(DEFAULT_BROKER_ROOT_PATH),
        output_path=str(DEFAULT_OUTPUT_PATH),
        static_version=get_static_version(),
    )


@app.get("/application-testing")
def application_testing():
    """Render the Application Testing page."""
    return render_template("application_testing.html")


def parse_test_catalog() -> list[dict[str, str]]:
    """Load test cases from testapp.md."""
    if not TEST_CATALOG_PATH.is_file():
        return []

    test_cases: list[dict[str, str]] = []
    for line in TEST_CATALOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| TC-"):
            continue

        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if len(columns) < 4:
            continue

        test_cases.append(
            {
                "id": columns[0],
                "name": columns[1].strip("`"),
                "description": columns[2],
                "expected_output": columns[3],
            }
        )

    return test_cases


def iter_test_ids(test_suite):
    """Yield fully qualified unittest IDs from a suite tree."""
    for test in test_suite:
        if hasattr(test, "__iter__"):
            yield from iter_test_ids(test)
        else:
            yield test.id()


def get_test_id_by_name() -> dict[str, str]:
    """Map short test function names to fully qualified unittest IDs."""
    import unittest

    suite = unittest.defaultTestLoader.discover(str(TESTS_PATH))
    test_ids = {}
    for test_id in iter_test_ids(suite):
        short_name = test_id.rsplit(".", 1)[-1]
        test_ids.setdefault(short_name, test_id)
    return test_ids


def parse_unittest_results(output: str) -> dict[str, str]:
    """Parse unittest verbose output into short test name statuses."""
    results: dict[str, str] = {}
    result_pattern = re.compile(
        r"^(?P<name>test_[\w_]+)\s+\(.+\)\s+\.\.\.\s+(?P<status>ok|FAIL|ERROR|skipped .+)$"
    )
    for line in output.splitlines():
        match = result_pattern.match(line.strip())
        if not match:
            continue

        results[match.group("name")] = (
            "passed" if match.group("status") == "ok" else "failed"
        )
    return results


def run_unittest_command(test_name: str | None = None) -> dict[str, object]:
    """Run all tests or one named test case in a subprocess."""
    command = [sys.executable, "-m", "unittest"]
    if test_name:
        test_id = get_test_id_by_name().get(test_name)
        if not test_id:
            return {
                "ok": False,
                "error": f"Unknown test case: {test_name}",
                "results": {},
                "output": "",
            }
        command.extend([test_id, "-v"])
    else:
        command.extend(["discover", "-s", "tests", "-v"])

    python_path = os.pathsep.join(
        [
            str(PROJECT_ROOT),
            str(TESTS_PATH),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    environment = {
        **os.environ,
        "PYTHONPATH": python_path,
        "PYTHONWARNINGS": "ignore::ResourceWarning",
    }

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return {
        "ok": completed.returncode == 0,
        "results": parse_unittest_results(output),
        "output": output,
    }


@app.get("/api/tests")
def tests_api():
    """Return the application test catalogue."""
    return jsonify({"tests": parse_test_catalog()})


@app.post("/api/tests/run")
def run_tests_api():
    """Run all tests or a single test case."""
    payload = request.get_json(silent=True) or {}
    test_name = payload.get("test_name")
    if test_name is not None and not isinstance(test_name, str):
        return jsonify({"error": "test_name must be a string."}), 400

    try:
        result = run_unittest_command(test_name)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "The test run timed out."}), 500

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@app.get("/api/run-report")
def run_report_api():
    """Run the parser workflow and return its output for the frontend."""
    try:
        report = run_report_with_console_output(Path(DEFAULT_BROKER_ROOT_PATH))
    except Exception as error:
        return (
            jsonify(
                {
                    "error": get_user_friendly_error_message(error),
                    "error_type": error.__class__.__name__,
                }
            ),
            500,
        )

    return jsonify(report)


def delete_files_in_folder(folder_path: Path) -> dict[str, object]:
    """Delete files under a configured folder without removing the folder itself."""
    ensure_folder_exists(folder_path)
    deleted_files: list[str] = []
    failed_files: list[dict[str, str]] = []

    gc.collect()

    for path in sorted(folder_path.rglob("*")):
        if not path.is_file():
            continue

        relative_path = str(path.relative_to(folder_path))
        last_error: OSError | None = None
        for _ in range(3):
            try:
                path.unlink()
                deleted_files.append(relative_path)
                last_error = None
                break
            except OSError as error:
                last_error = error
                gc.collect()
                time.sleep(0.2)

        if last_error is not None:
            failed_files.append({"file": relative_path, "error": str(last_error)})

    return {
        "folder": str(folder_path),
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
        "failed_count": len(failed_files),
        "failed_files": failed_files,
    }


@app.post("/api/delete-broker-files")
def delete_broker_files_api():
    """Delete uploaded source files from the configured broker input folders."""
    try:
        results = {
            "poems": delete_files_in_folder(DEFAULT_POEMS_PATH),
            "interactive_brokers": delete_files_in_folder(
                DEFAULT_INTERACTIVE_BROKERS_PATH
            ),
        }
    except OSError as error:
        return jsonify({"error": str(error)}), 500

    deleted_count = sum(result["deleted_count"] for result in results.values())
    failed_count = sum(result["failed_count"] for result in results.values())
    return jsonify(
        {
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "results": results,
        }
    )


@app.post("/api/delete-output-files")
def delete_output_files_api():
    """Delete generated files from the configured Output folder."""
    try:
        result = delete_files_in_folder(DEFAULT_OUTPUT_PATH)
    except OSError as error:
        return jsonify({"error": str(error)}), 500

    return jsonify(
        {
            "deleted_count": result["deleted_count"],
            "failed_count": result["failed_count"],
            "result": result,
        }
    )


@app.post("/api/upload-files")
def upload_files_api():
    """Upload broker files into the configured source folders."""
    saved_files: dict[str, list[str]] = {
        "poems_files": [],
        "interactive_brokers_files": [],
    }
    rejected_files: list[str] = []

    for field_name, target in UPLOAD_TARGETS.items():
        uploaded_files = request.files.getlist(field_name)
        ensure_folder_exists(target["folder"])
        allowed_extensions = target["extensions"]
        label = target["label"]

        for uploaded_file in uploaded_files:
            if not uploaded_file or not uploaded_file.filename:
                continue

            original_name = uploaded_file.filename
            safe_name = secure_filename(original_name)
            extension = Path(safe_name).suffix.lower()
            if not safe_name or extension not in allowed_extensions:
                rejected_files.append(f"{original_name} is not a supported {label} file.")
                continue

            destination = target["folder"] / safe_name
            uploaded_file.save(destination)
            saved_files[field_name].append(safe_name)

    if not saved_files["poems_files"] and not saved_files["interactive_brokers_files"]:
        return (
            jsonify(
                {
                    "error": "No supported files were uploaded.",
                    "rejected_files": rejected_files,
                    "saved_files": saved_files,
                }
            ),
            400,
        )

    return jsonify(
        {
            "saved_files": saved_files,
            "rejected_files": rejected_files,
        }
    )


@app.get("/outputs/<path:filename>")
def output_file(filename: str):
    """Serve generated CSV and PNG files from the configured Output folder."""
    if filename == DEFAULT_STOCK_CODE_MAPPING_PATH.name:
        return send_from_directory(DEFAULT_STOCK_CODE_MAPPING_PATH.parent, filename)

    return send_from_directory(DEFAULT_OUTPUT_PATH, filename)
