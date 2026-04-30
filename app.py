# This module is the project-root Flask launcher. The web application lives in
# portfolio_tracker.web so the repository root can stay small while existing
# commands such as `python .\app.py` continue to work.

from __future__ import annotations

import os

from portfolio_tracker.web import app


if __name__ == "__main__":
    app.run(
        debug=True,
        port=int(os.environ.get("PORT", "5000")),
        use_reloader=False,
    )
