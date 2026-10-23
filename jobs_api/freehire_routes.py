"""
Routes that query the Freehire API (https://freehire.me) for jobs, running
position x country searches concurrently in a thread pool.
"""

import math

import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Query

from .common import clean_nans
from .config import DEFAULT_POSITIONS, DEFAULT_COUNTRY_CODES, DEFAULT_HOURS, DEFAULT_LIMIT

router = APIRouter()

BASE_API_URL = "https://freehire.me/api/v1/jobs/search"

DEFAULT_MAX_WORKERS = 4
DEFAULT_DAYS = math.ceil(DEFAULT_HOURS / 24)


def fetch_one(position: str, country: str, posted_within_days: int, limit: int):
    params = {
        "q": position,
        "countries": country,
        "posted_within_days": posted_within_days,
        "limit": limit,
    }

    print(f"[freehire] Fetching '{position}' in country '{country}'...")
    try:
        response = requests.get(BASE_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            jobs = data
        elif isinstance(data, dict):
            jobs = data.get("jobs", data.get("results", data.get("data", [])))
            if not isinstance(jobs, list):
                jobs = [data]
        else:
            jobs = []

        print(f"[freehire]   -> done: {len(jobs)} jobs for '{position}' in '{country}'")
        return position, country, jobs, None
    except Exception as e:
        print(f"[freehire]   -> FAILED: '{position}' in '{country}': {e}")
        return position, country, [], str(e)


@router.get("/freehire")
def freehire(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles/queries"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_CODES), description="Comma-separated list of country codes"),
    posted_within_days: int = Query(DEFAULT_DAYS, description="Filter jobs posted within X days"),
    limit: int = Query(DEFAULT_LIMIT, description="Max results per individual query"),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent API requests"),
):
    position_list = [p.strip() for p in positions.split(",") if p.strip()]
    country_list = [c.strip() for c in countries.split(",") if c.strip()]

    tasks = [(position, country) for position in position_list for country in country_list]

    print(f"=== Starting Freehire API fetch ({len(tasks)} requests, {max_workers} workers) ===")

    all_jobs = []
    errors = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_one, position, country, posted_within_days, limit)
            for position, country in tasks
        ]

        for future in as_completed(futures):
            position, country, jobs, error = future.result()
            if error:
                errors[f"{position} | {country}"] = error
            else:
                for job in jobs:
                    if isinstance(job, dict):
                        job["search_position"] = position
                        job["search_country"] = country
                        all_jobs.append(job)

    if not all_jobs:
        return {"total": 0, "jobs": [], "errors": errors}

    df = pd.DataFrame(all_jobs)

    for url_col in ["job_url", "url", "link", "id"]:
        if url_col in df.columns:
            df = df.drop_duplicates(subset=[url_col])
            break

    cleaned_jobs = clean_nans(df.to_dict(orient="records"))

    print(f"=== Freehire API finished: {len(cleaned_jobs)} unique jobs combined ===")

    return {
        "total": len(cleaned_jobs),
        "jobs": cleaned_jobs,
        "errors": errors,
    }
