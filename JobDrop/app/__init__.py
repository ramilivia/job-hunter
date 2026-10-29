"""
FastAPI wrapper that exposes JobDrop's Wellfound (formerly AngelList) scraper
over HTTP, for use by n8n's HTTP Request node or any other consumer.

This is intentionally a separate project from the JobSpy ``jobs_api`` because
JobSpy and JobDrop pin incompatible versions of ``curl_cffi`` and cannot be
installed in the same virtualenv.

Setup:
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

Run:
    python3 -m app

Then call it, e.g.:
    GET http://localhost:8001/wellfound?positions=Engineering%20Manager&hours_old=168&is_remote=true
"""

from fastapi import FastAPI

from .wellfound_routes import router as wellfound_router
from .adzuna_routes import router as adzuna_router
from .builtin_routes import router as builtin_router

app = FastAPI()
app.include_router(wellfound_router)
app.include_router(adzuna_router)
app.include_router(builtin_router)
