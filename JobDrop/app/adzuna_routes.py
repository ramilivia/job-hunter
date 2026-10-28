"""
Routes that drive jobdrop's Adzuna scraper over HTTP.

Adzuna is a large free aggregator with rich salary data (~100% salary fill
rate). jobdrop's scraper is a plain HTTP API call (no Camoufox, sub-second per
call) and reads its credentials from the ADZUNA_APP_ID / ADZUNA_APP_KEY env
vars, falling back to bundled defaults when absent.

Country selection is via ``country_indeed`` (jobdrop maps the country name to a
2-char Adzuna code internally), NOT ``location`` — ``location`` becomes
Adzuna's free-text ``where``. Countries Adzuna doesn't map are rejected up
front and reported in ``errors`` rather than silently falling back to US jobs.
"""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Query
from jobdrop import scrape_jobs

from jobdrop.adzuna import _COUNTRY_MAP
from jobdrop.model import Country

from .common import json_safe_jobs
from .config import DEFAULT_COUNTRY_NAMES, DEFAULT_HOURS, DEFAULT_LIMIT, DEFAULT_POSITIONS
from .wellfound_routes import normalize_record

router = APIRouter()

DEFAULT_MAX_WORKERS = 4


def _resolve_adzuna_country(name: str) -> tuple[str | None, str | None]:
    """Map a config country name to an Adzuna 2-char code via jobdrop's map.

    Returns (adzuna_code, error). jobdrop's Adzuna scraper silently falls back
    to the US code for any country it doesn't map, so we resolve up front and
    reject unmapped countries instead of returning US jobs mislabeled with the
    requested country.
    """
    try:
        country_enum = Country.from_string(name)
    except ValueError:
        return None, f"unknown country '{name}'"
    code = _COUNTRY_MAP.get(country_enum)
    if code is None:
        return None, f"Adzuna does not support '{name}'"
    return code, None


def scrape_one(position: str, country: str, results_wanted: int, hours_old: int, is_remote: bool):
    print(f"[adzuna] Starting '{position}' in {country}...")
    try:
        jobs = scrape_jobs(
            site_name="adzuna",
            search_term=position,
            country_indeed=country,
            results_wanted=results_wanted,
            hours_old=hours_old,
            is_remote=is_remote,
        )
        jobs["search_position"] = position
        jobs["search_country"] = country
        print(f"[adzuna]   -> done: {len(jobs)} jobs for '{position}' in {country}")
        return position, country, jobs, None
    except Exception as e:
        print(f"[adzuna]   -> FAILED: '{position}' in {country}: {e}")
        return position, country, None, str(e)


@router.get("/adzuna")
def adzuna(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles, searched one at a time"),
    countries: str = Query(",".join(DEFAULT_COUNTRY_NAMES), description="Comma-separated list of countries"),
    results_wanted: int = Query(DEFAULT_LIMIT),
    hours_old: int = Query(DEFAULT_HOURS, description="Drop postings older than N hours"),
    is_remote: bool = Query(False, description="Only return remote roles"),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent scrapes"),
):
    position_list = [p.strip() for p in positions.split(",") if p.strip()]
    country_list = [c.strip() for c in countries.split(",") if c.strip()]

    # Reject countries Adzuna can't query before they silently fall back to US.
    errors: dict[str, str] = {}
    valid_countries: list[str] = []
    for country in country_list:
        _, error = _resolve_adzuna_country(country)
        if error:
            errors[f"* | {country}"] = error
        else:
            valid_countries.append(country)

    tasks = [(position, country) for position in position_list for country in valid_countries]

    print(f"=== Starting Adzuna scrape ({len(tasks)} searches, {max_workers} workers) ===")
    print(f"Positions: {', '.join(position_list)}")
    print(f"Countries: {', '.join(valid_countries)}")

    all_jobs: list[dict] = []

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
        print("=== Adzuna scrape finished: 0 jobs ===")
        return {"total": 0, "jobs": [], "errors": errors}

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"])

    records: list[dict] = []
    for record in combined.to_dict(orient="records"):
        records.append(normalize_record(record))

    cleaned_jobs = json_safe_jobs(records, errors)

    print(f"=== Adzuna scrape finished: {len(cleaned_jobs)} unique jobs ===")

    return {
        "total": len(cleaned_jobs),
        "jobs": cleaned_jobs,
        "errors": errors,
    }