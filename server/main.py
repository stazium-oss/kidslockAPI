"""
KidLock Server — FastAPI application.
Run with: uvicorn main:app --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from api import router

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="KidLock",
    description="Parental control API",
    version="2.0",
    docs_url="/api/docs",
)

# CORS — allow local network and Tailscale IPs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve static files (web panel)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
def serve_panel():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health")
def health():
    return {"status": "ok"}
