# This module provides the Flask web server for Portfolio Tracker. It serves
# the browser UI, runs the parser workflow on demand, and exposes generated
# Output files so users can inspect CSV and chart results from the web app.

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from constants import (
    CSV_EXTENSIONS,
    DEFAULT_BROKER_ROOT_PATH,
    DEFAULT_INTERACTIVE_BROKERS_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_POEMS_PATH,
    EXCEL_EXTENSIONS,
)
from file_helpers import ensure_folder_exists
from parse_broker_reports import get_user_friendly_error_message
from report_runner import run_report_with_console_output


app = Flask(__name__)


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


@app.get("/")
def index():
    """Render the Portfolio Tracker web app."""
    return render_template(
        "index.html",
        default_root_path=str(DEFAULT_BROKER_ROOT_PATH),
        output_path=str(DEFAULT_OUTPUT_PATH),
    )


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
    return send_from_directory(DEFAULT_OUTPUT_PATH, filename)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
