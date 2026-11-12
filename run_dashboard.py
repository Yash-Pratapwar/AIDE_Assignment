#!/usr/bin/env python3
"""Launcher for the Kestrel Provisions Executive Analytics Dashboard."""

import argparse
import http.server
import socketserver
import webbrowser
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DASHBOARD_FILE = PROJECT_DIR / "dashboard.html"

def main():
    parser = argparse.ArgumentParser(description="View or serve the Kestrel Provisions Executive Dashboard")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve dashboard on (default: 8000)")
    parser.add_argument("--server", action="store_true", help="Start a local HTTP server instead of opening file directly")
    args = parser.parse_args()

    if not DASHBOARD_FILE.is_file():
        print("Dashboard not found. Regenerating dashboard from curated DuckDB tables...")
        import generate_dashboard
        generate_dashboard.main()

    if args.server:
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

        class Handler(QuietHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(PROJECT_DIR), **kw)

        url = f"http://localhost:{args.port}/dashboard.html"
        print(f"\n=======================================================")
        print(f"  Kestrel Provisions Executive Analytics Dashboard")
        print(f"  Local Server: {url}")
        print(f"  Press Ctrl+C to stop the server")
        print(f"=======================================================\n")
        webbrowser.open(url)
        with socketserver.TCPServer(("", args.port), Handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
    else:
        file_url = DASHBOARD_FILE.as_uri()
        print(f"Opening dashboard in default web browser: {file_url}")
        webbrowser.open(file_url)

if __name__ == "__main__":
    main()
