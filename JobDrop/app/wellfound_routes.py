"""
Routes that drive JobDrop's Wellfound scraper over HTTP.

Wellfound (formerly AngelList) is a startup job board. JobDrop scrapes it
with Camoufox (a patched Firefox) because the /role/* routes are behind a
DataDome WAF. The first call downloads ~300MB patched Firefox on demand, so
the first request is slow and each page render takes ~5-6s.

Why this lives in a separate project from the JobSpy ``jobs_api``: JobSpy
pins ``curl_cffi>=0.16.2`` while JobDrop pins ``curl-cffi<0.8.0,>=0.7.0``.
The two libraries cannot be installed together, so JobDrop must run in its
own virtualenv/project exposing its own HTTP endpoint.
"""

import math
from typing import Any

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Query

from jobdrop import scrape_jobs

from .common import json_safe_jobs
from .config import DEFAULT_COUNTRY_NAMES, DEFAULT_LIMIT, DEFAULT_POSITIONS, WELLFOUND_DEFAULT_HOURS

router = APIRouter()

# Wellfound renders slowly (~5-6s/page) and is fronted by DataDome, so we keep
# concurrency modest to avoid tripping the bot detection.
DEFAULT_MAX_WORKERS = 3


def _norm_location(loc: Any) -> str | None:
    """JobDrop flattens location to a 'City, State, Country' string already;
    this just guards against empty/None values."""
    loc = str(loc).strip() if loc is not None else ""
    return loc or None


def scrape_one(position: str, country: str, results_wanted: int, hours_old: int, is_remote: bool):
    print(f"[wellfound] Starting '{position}' in {country}...")
    try:
        jobs = scrape_jobs(
            site_name=["wellfound"],
            search_term=position,
            location=country,
            results_wanted=results_wanted,
            hours_old=hours_old,
            is_remote=is_remote,
        )
        jobs["search_position"] = position
        jobs["search_country"] = country
        print(f"[wellfound]   -> done: {len(jobs)} jobs for '{position}' in {country}")
        return position, country, jobs, None
    except Exception as e:
        print(f"[wellfound]   -> FAILED: '{position}' in {country}: {e}")
        return position, country, None, str(e)


@router.get("/wellfound")
def wellfound(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles, searched one at a time"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_NAMES), description="Comma-separated list of countries (or free-text locations)"),
    results_wanted: int = Query(DEFAULT_LIMIT),
    hours_old: int | None = Query(WELLFOUND_DEFAULT_HOURS, description="Drop postings older than N hours (omit for no recency filter)"),
    is_remote: bool = Query(False, description="Only return remote roles"),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent scrapes"),
):
    position_list = [p.strip() for p in positions.split(",") if p.strip()]
    country_list = [c.strip() for c in countries.split(",") if c.strip()]

    tasks = [(position, country) for position in position_list for country in country_list]

    print(f"=== Starting Wellfound scrape ({len(tasks)} searches, {max_workers} workers) ===")
    print(f"Positions: {', '.join(position_list)}")
    print(f"Countries: {', '.join(country_list)}")

    all_jobs: list[dict] = []
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
        print("=== Wellfound scrape finished: 0 jobs ===")
        return {"total": 0, "jobs": [], "errors": errors}

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"])

    # JobDrop only read 'site' from the dataframe columns. Normalize the fields
    # into the same shape the JobSpy jobs_api returns so n8n/pipelines that
    # consume both services see a consistent schema.
    records: list[dict] = []
    for record in combined.to_dict(orient="records"):
        records.append(normalize_record(record))

    cleaned_jobs = json_safe_jobs(records, errors)

    print(f"=== Wellfound scrape finished: {len(cleaned_jobs)} unique jobs ===")

    return {
        "total": len(cleaned_jobs),
        "jobs": cleaned_jobs,
        "errors": errors,
    }


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Clean JobDrop's dataframe row for JSON serialization.

    JobDrop's column names already match the JobSpy jobs_api schema (``title``,
    ``company``, ``job_url``, ...); this step only normalizes types: ``job_type``
    is a comma-joined string -> list, ``date_posted`` -> ISO string, and any
    NaN/Inf floats are dropped (json_safe_jobs also handles this downstream).
    """
    out: dict[str, Any] = {}

    for key, value in record.items():
        if value is None:
            continue

        if key == "job_type" and isinstance(value, str):
            # JobDrop emits JobType enum members as a comma-joined string, e.g.
            # "fulltime,parttime". Keep as a clean list for JSON consumers.
            out[key] = [part.strip() for part in value.split(",") if part.strip()]
        elif key == "date_posted" and hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            continue
        else:
            out[key] = value

    out["location"] = _norm_location(out.get("location"))
    return out