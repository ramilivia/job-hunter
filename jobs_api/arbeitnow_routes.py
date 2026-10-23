"""
Routes that query the Arbeitnow job board API (https://www.arbeitnow.com/api/job-board-api).

Arbeitnow has no server-side search/position filter (its `search`/`tags` params
are silently ignored) and no page count up front - pagination just ends when a
page comes back with no `next` link / no jobs. So this walks every page in
concurrent batches, then filters locally by the same `positions` used by the
other routes, matched against the job title+description.
"""

import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query

from .common import clean_nans
from .config import DEFAULT_POSITIONS

router = APIRouter()

BASE_API_URL = "https://www.arbeitnow.com/api/job-board-api"

DEFAULT_MAX_WORKERS = 3  # Arbeitnow's API terms ask not to abuse it; keep this modest
DEFAULT_MAX_PAGES = 50  # safety net in case the API never stops paginating


def fetch_page(page: int):
    print(f"[arbeitnow] Fetching page {page}...")
    try:
        response = requests.get(BASE_API_URL, params={"page": page}, timeout=30)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("data", []) if isinstance(data, dict) else []
        has_next = bool(data.get("links", {}).get("next")) if isinstance(data, dict) else False
        print(f"[arbeitnow]   -> done: {len(jobs)} jobs on page {page}")
        return page, jobs, has_next, None
    except Exception as e:
        print(f"[arbeitnow]   -> FAILED: page {page}: {e}")
        return page, [], False, str(e)


def fetch_all_pages(max_workers: int, max_pages: int):
    """Walk pages in batches of max_workers until a page has no jobs / no next link."""
    all_jobs = []
    errors = {}

    page_cursor = 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while page_cursor <= max_pages:
            batch_pages = range(page_cursor, min(page_cursor + max_workers, max_pages + 1))
            results = sorted(executor.map(fetch_page, batch_pages), key=lambda r: r[0])

            reached_end = False
            for page, jobs, has_next, error in results:
                if error:
                    errors[f"page {page}"] = error
                    continue
                all_jobs.extend(job for job in jobs if isinstance(job, dict))
                if not jobs or not has_next:
                    reached_end = True

            if reached_end:
                break
            page_cursor += max_workers

    return all_jobs, errors


def matches_positions(job: dict, positions: list[str]) -> bool:
    if not positions:
        return True
    haystack = f"{job.get('title', '')} {job.get('description', '')}".lower()
    return any(position.lower() in haystack for position in positions)


@router.get("/arbeitnow")
def arbeitnow(
    positions: str = Query(",".join(DEFAULT_POSITIONS), description="Comma-separated list of job titles/queries to filter by"),
    remote_only: bool = Query(False, description="Only return remote jobs"),
    max_workers: int = Query(DEFAULT_MAX_WORKERS, description="Number of concurrent page fetches"),
    max_pages: int = Query(DEFAULT_MAX_PAGES, description="Safety cap on how many pages to walk"),
):
    position_list = [p.strip() for p in positions.split(",") if p.strip()]

    print(f"=== Starting Arbeitnow API fetch (all pages, {max_workers} workers) ===")

    fetched_jobs, errors = fetch_all_pages(max_workers, max_pages)

    all_jobs = [
        job for job in fetched_jobs
        if (not remote_only or job.get("remote"))
        and matches_positions(job, position_list)
    ]

    if not all_jobs:
        return {"total": 0, "jobs": [], "errors": errors}

    df = pd.DataFrame(all_jobs)

    for url_col in ["slug", "url", "job_url", "id"]:
        if url_col in df.columns:
            df = df.drop_duplicates(subset=[url_col])
            break

    cleaned_jobs = clean_nans(df.to_dict(orient="records"))

    print(f"=== Arbeitnow API finished: {len(cleaned_jobs)} unique jobs ===")

    return {
        "total": len(cleaned_jobs),
        "jobs": cleaned_jobs,
        "errors": errors,
    }
