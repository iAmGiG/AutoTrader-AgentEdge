#!/usr/bin/env python3
"""GEX Visualizer - FastAPI Server.

Serves static files and provides foundation for future API endpoints.
Run with: python server.py
"""

import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Configuration
PORT = 8080
HOST = "127.0.0.1"
WEB_DIR = Path(__file__).parent.absolute()

# FastAPI app
app = FastAPI(
    title="GEX Visualizer",
    description="Gamma Exposure visualization tool",
    version="1.0.0",
)

# Serve static files (CSS, JS, data)
app.mount("/css", StaticFiles(directory=WEB_DIR / "css"), name="css")
app.mount("/data", StaticFiles(directory=WEB_DIR / "data"), name="data")


# Serve JS files and other static assets from root
@app.get("/")
async def root():
    """Serve the main HTML file."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/{filename:path}")
async def static_files(filename: str):
    """Serve static files from the visualizer directory."""
    file_path = WEB_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(WEB_DIR / "index.html")


def main():
    """Start server and open browser."""
    url = f"http://{HOST}:{PORT}"
    print(f"GEX Visualizer: {url}")
    print("Press Ctrl+C to stop\n")

    # Open browser
    webbrowser.open(url)

    # Run server
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
