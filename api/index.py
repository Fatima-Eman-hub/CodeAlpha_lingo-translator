"""
Vercel serverless entry point.

Vercel's Python runtime auto-detects any file under /api ending in .py and,
if it defines a WSGI-compatible `app` variable, wraps it as a serverless
function. This file just imports our real Flask app from backend/app.py —
all actual route logic lives there, unchanged from local/Render/Back4app
deployments.

vercel.json rewrites every /api/* request to this one file, so Flask's own
router (the @app.route(...) decorators in backend/app.py) handles the
sub-paths (/api/translate, /api/history, etc.) exactly like it does locally.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import app  # noqa: E402  (Flask app instance — Vercel's Python runtime looks for this name)
