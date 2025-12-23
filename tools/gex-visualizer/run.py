#!/usr/bin/env python3
"""GEX Visualizer - Development Server.

Tries to use FastAPI (recommended) with fallback to stdlib http.server.
Install FastAPI for best experience: pip install fastapi uvicorn
"""

import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

import uvicorn
from server import app

PORT = 8080
HOST = "127.0.0.1"
WEB_DIR = Path(__file__).parent.absolute()


def run_fastapi():
    """Run FastAPI server (recommended)."""

    url = f"http://{HOST}:{PORT}"
    print(f"GEX Visualizer (FastAPI): {url}")
    print("Press Ctrl+C to stop\n")
    webbrowser.open(url)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def run_simple():
    """Fallback to stdlib http.server."""

    os.chdir(WEB_DIR)
    handler = http.server.SimpleHTTPRequestHandler

    with socketserver.TCPServer(("", PORT), handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"GEX Visualizer (Simple): {url}")
        print("Tip: pip install fastapi uvicorn for better server")
        print("Press Ctrl+C to stop")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main():
    """Start the best available server."""
    try:
        run_fastapi()
    except ImportError:
        run_simple()


if __name__ == "__main__":
    main()
