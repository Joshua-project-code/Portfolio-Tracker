# This module provides the Flask web server for Portfolio Tracker. It serves
# the browser UI, runs the parser workflow on demand, and exposes generated
# Output files so users can inspect CSV and chart results from the web app.

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, send_from_directory

from constants import DEFAULT_BROKER_ROOT_PATH, DEFAULT_OUTPUT_PATH
from parse_broker_reports import (
    get_user_friendly_error_message,
    run_report_with_console_output,
)


app = Flask(__name__)


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


@app.get("/outputs/<path:filename>")
def output_file(filename: str):
    """Serve generated CSV and PNG files from the configured Output folder."""
    return send_from_directory(DEFAULT_OUTPUT_PATH, filename)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
