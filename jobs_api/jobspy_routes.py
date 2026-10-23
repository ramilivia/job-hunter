"""
Routes that drive JobSpy's own scrapers (LinkedIn, Indeed) over HTTP, running
position x country searches concurrently in a thread pool.
"""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Query
from jobspy import scrape_jobs

from .common import json_safe_jobs
from .config import DEFAULT_POSITIONS, DEFAULT_COUNTRY_NAMES, DEFAULT_HOURS, DEFAULT_LIMIT

router = APIRouter()

DEFAULT_MAX_WORKERS = 3


def scrape_one(site: str, position: str, country: str, results_wanted: int, hours_old: int, is_remote: bool):
    print(f"[{site}] Starting '{position}' in {country}...")
    try:
        jobs = scrape_jobs(
            site_name=[site],
            search_term=position,
            location=country,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed=country if site in ("indeed", "glassdoor") else None,
            is_remote=is_remote,
            linkedin_fetch_description=True,
            retry=True,
        )
        jobs["search_position"] = position
        jobs["search_country"] = country
        print(f"[{site}]   -> done: {len(jobs)} jobs for '{position}' in {country}")
        return position, country, jobs, None
    except Exception as e:
        print(f"[{site}]   -> FAILED: '{position}' in {country}: {e}")
        return position, country, None, str(e)


def run_scrape(site: str, positions: str, countries: str, results_wanted: int, hours_old: int, is_remote: bool, max_workers: int):
    position_list = [p.strip() for p in positions.split(",") if p.strip()]
    country_list = [c.strip() for c in countries.split(",") if c.strip()]

    tasks = [(position, country) for position in position_list for country in country_list]

    print(f"=== Starting {site} scrape ({len(tasks)} searches, {max_workers} workers) ===")
    print(f"Positions: {', '.join(position_list)}")
    print(f"Countries: {', '.join(country_list)}")

    all_jobs = []
    errors = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(scrape_one, site, position, country, results_wanted, hours_old, is_remote)
            for position, country in tasks
        ]

        for future in as_completed(futures):
            position, country, jobs, error = future.result()
            if error:
                errors[f"{position} | {country}"] = error
            else:
                all_jobs.append(jobs)

    if not all_jobs:
        print(f"=== {site} scrape finished: 0 jobs ===")
        return {"total": 0, "jobs": [], "errors": errors}

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"])

    jobs = json_safe_jobs(combined.to_dict(orient="records"), errors)

    print(f"=== {site} scrape finished: {len(jobs)} jobs ===")

    return {
        "total": len(jobs),
        "jobs": jobs,
        "errors": errors,
    }


@router.get("/linkedin")
def linkedin(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles, searched one at a time"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_NAMES), description="Comma-separated list of countries"),
    results_wanted: int = Query(DEFAULT_LIMIT),
    hours_old: int = Query(DEFAULT_HOURS),
    is_remote: bool = Query(False),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent scrapes"),
):
    return run_scrape("linkedin", positions, countries, results_wanted, hours_old, is_remote, max_workers)


@router.get("/indeed")
def indeed(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles, searched one at a time"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_NAMES), description="Comma-separated list of countries"),
    results_wanted: int = Query(DEFAULT_LIMIT),
    hours_old: int = Query(DEFAULT_HOURS),
    is_remote: bool = Query(False),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent scrapes"),
):
    return run_scrape("indeed", positions, countries, results_wanted, hours_old, is_remote, max_workers)


@router.get("/google")
def google(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles, searched one at a time"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_NAMES), description="Comma-separated list of countries"),
    results_wanted: int = Query(DEFAULT_LIMIT),
    hours_old: int = Query(DEFAULT_HOURS),
    is_remote: bool = Query(False),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent scrapes"),
):
    return run_scrape("google", positions, countries, results_wanted, hours_old, is_remote, max_workers)


@router.get("/glassdoor")
def glassdoor(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles, searched one at a time"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_NAMES), description="Comma-separated list of countries (Glassdoor only supports some, e.g. Austria, Germany, Italy, Netherlands, Spain, Switzerland)"),
    results_wanted: int = Query(DEFAULT_LIMIT),
    hours_old: int = Query(DEFAULT_HOURS),
    is_remote: bool = Query(False),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent scrapes"),
):
    return run_scrape("glassdoor", positions, countries, results_wanted, hours_old, is_remote, max_workers)
