"""
Routes that drive jobdrop's Built In scraper over HTTP.

Built In (builtin.com) is a family of tech-vetted local job boards
(Built In NYC/LA/Chicago/Atlanta/etc.). jobdrop scrapes its server-rendered
HTML directly (no Camoufox, sub-second per call) and cross-source dedups its
results against LinkedIn/Indeed via (company, title), so Built In contributes
its tech-quality filter without inflating result counts.

Country filtering note: jobdrop's Built In scraper emits ``location=`` in its
query string, but Built In ignores that param. Its frontend actually filters by
``country=<ISO alpha-3>`` (e.g. ``country=DEU``) and encodes remote as a
``/jobs/remote`` path segment. We monkeypatch the scraper's URL builder here so
the country/remote filters actually take effect, mapping the shared config's
country names/codes to their ISO alpha-3 codes.
"""

from urllib.parse import quote_plus

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Query
from jobdrop import scrape_jobs
from jobdrop.builtin import BuiltIn

from .common import json_safe_jobs
from .config import (
    COUNTRY_ALPHA3_LOOKUP,
    DEFAULT_COUNTRY_NAMES,
    DEFAULT_HOURS,
    DEFAULT_LIMIT,
    DEFAULT_POSITIONS,
)
from .wellfound_routes import normalize_record

router = APIRouter()

# Built In serves plain HTML, so a modest pool is plenty.
DEFAULT_MAX_WORKERS = 4


def _resolve_alpha3(location: str | None) -> str | None:
    """Map a free-text location (country name or alpha-2 code) to ISO alpha-3."""
    if not location:
        return None
    return COUNTRY_ALPHA3_LOOKUP.get(location.strip().lower())


def _patched_build_search_url(self, si, page: int) -> str:
    """Replacement for BuiltIn._build_search_url that matches Built In's frontend.

    Uses ``country=<ISO alpha-3>`` for location filtering (the param their UI
    emits) and the ``/jobs/remote`` path segment for the remote filter, both of
    which jobdrop's stock builder gets wrong.
    """
    base = "https://builtin.com/jobs"
    if si.is_remote:
        base += "/remote"
    params = []
    if si.search_term:
        params.append(f"search={quote_plus(si.search_term)}")
    alpha3 = _resolve_alpha3(si.location)
    if alpha3:
        params.append(f"country={alpha3}")
    elif si.location:
        params.append(f"location={quote_plus(si.location)}")
    if page > 1:
        params.append(f"page={page}")
    suffix = ("?" + "&".join(params)) if params else ""
    return f"{base}{suffix}"


# Apply the patch once at import time, before any scrape runs.
BuiltIn._build_search_url = _patched_build_search_url


def scrape_one(position: str, country: str, results_wanted: int, hours_old: int, is_remote: bool):
    print(f"[builtin] Starting '{position}' in {country}...")
    try:
        jobs = scrape_jobs(
            site_name="builtin",
            search_term=position,
            location=country,
            results_wanted=results_wanted,
            hours_old=hours_old,
            is_remote=is_remote,
        )
        jobs["search_position"] = position
        jobs["search_country"] = country
        print(f"[builtin]   -> done: {len(jobs)} jobs for '{position}' in {country}")
        return position, country, jobs, None
    except Exception as e:
        print(f"[builtin]   -> FAILED: '{position}' in {country}: {e}")
        return position, country, None, str(e)


@router.get("/builtin")
def builtin(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles, searched one at a time"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_NAMES), description="Comma-separated list of countries (or free-text locations)"),
    results_wanted: int = Query(DEFAULT_LIMIT),
    hours_old: int = Query(DEFAULT_HOURS, description="Drop postings older than N hours"),
    is_remote: bool = Query(False, description="Only return remote roles"),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent scrapes"),
):
    position_list = [p.strip() for p in positions.split(",") if p.strip()]
    country_list = [c.strip() for c in countries.split(",") if c.strip()]

    tasks = [(position, country) for position in position_list for country in country_list]

    print(f"=== Starting Built In scrape ({len(tasks)} searches, {max_workers} workers) ===")
    print(f"Positions: {', '.join(position_list)}")
    print(f"Countries: {', '.join(country_list)}")

    all_jobs: list[pd.DataFrame] = []
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(scrape_one, position, country, results_wanted, hours_old, is_remote)
            for position, country in tasks
        ]

        for future in as_completed(futures):
            position, country, jobs, error = future.result()
            if error:
                errors[f"{position} | {country}"] = error
            elif jobs is not None and not jobs.empty:
                all_jobs.append(jobs)

    if not all_jobs:
        print("=== Built In scrape finished: 0 jobs ===")
        return {"total": 0, "jobs": [], "errors": errors}

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"])

    records: list[dict] = []
    for record in combined.to_dict(orient="records"):
        records.append(normalize_record(record))

    cleaned_jobs = json_safe_jobs(records, errors)

    print(f"=== Built In scrape finished: {len(cleaned_jobs)} unique jobs ===")

    return {
        "total": len(cleaned_jobs),
        "jobs": cleaned_jobs,
        "errors": errors,
    }