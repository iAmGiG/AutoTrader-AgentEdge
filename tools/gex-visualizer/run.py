#!/usr/bin/env python3
"""Start local server for GEX Visualizer. Opens browser automatically."""

import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

PORT = 8080
WEB_DIR = Path(__file__).parent.absolute()

os.chdir(WEB_DIR)

handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), handler) as httpd:
    url = f"http://localhost:{PORT}"
    print(f"GEX Visualizer: {url}")
    print("Press Ctrl+C to stop")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
