"""
Small FastAPI wrapper that exposes job search over HTTP (e.g. for n8n's HTTP
Request node, since n8n's Python Code node runs in a sandbox and can't run
JobSpy or hit external APIs directly).

Setup (inside your existing jobspy repo + venv):
    source venv/bin/activate
    pip install fastapi uvicorn requests

Run:
    python3 -m jobs_api

Then call it, e.g.:
    GET http://localhost:8000/linkedin?countries=Germany,Netherlands&hours_old=168
    GET http://localhost:8000/indeed?countries=Germany,Netherlands&hours_old=168
    GET http://localhost:8000/freehire?countries=nl,de&posted_within_days=3
    GET http://localhost:8000/arbeitnow?pages=5&keywords=engineer&remote_only=true
"""

from fastapi import FastAPI

from .jobspy_routes import router as jobspy_router
from .freehire_routes import router as freehire_router
from .arbeitnow_routes import router as arbeitnow_router

app = FastAPI()
app.include_router(jobspy_router)
app.include_router(freehire_router)
app.include_router(arbeitnow_router)
