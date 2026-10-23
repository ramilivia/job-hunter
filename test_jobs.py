"""
Small FastAPI wrapper around JobSpy so it can be called over HTTP (e.g. from n8n's
HTTP Request node, since n8n's Python Code node runs in a sandbox and can't run
JobSpy directly).

Setup (inside your existing jobspy repo + venv):
    source venv/bin/activate
    pip install fastapi uvicorn

Run:
    python3 jobspy_api.py

Then call it, e.g.:
    GET http://localhost:8000/scrape?countries=Germany,Netherlands&hours_old=168
"""

import pandas as pd
from fastapi import FastAPI, Query
from jobspy import scrape_jobs

app = FastAPI()

DEFAULT_SEARCH_TERM = '"engineering manager" OR "solution architect" OR "staff engineer"'
DEFAULT_COUNTRIES = "Germany", "Netherlands", "Spain", "Ireland", "Austria", "Sweden", "Denmark", "Norway", "Poland"
DEFAULT_SITES = ["indeed", "linkedin"]


@app.get("/scrape")
def scrape(
    search_term: str = Query(DEFAULT_SEARCH_TERM),
    countries: str = Query(",".join(DEFAULT_COUNTRIES), description="Comma-separated list of countries"),
    sites: str = Query(",".join(DEFAULT_SITES), description="Comma-separated list of job sites"),
    results_wanted: int = Query(50),
    hours_old: int = Query(24),
    is_remote: bool = Query(False),
):
    country_list = [c.strip() for c in countries.split(",") if c.strip()]
    site_list = [s.strip() for s in sites.split(",") if s.strip()]

    all_jobs = []
    errors = {}

    for country in country_list:
        try:
            jobs = scrape_jobs(
                site_name=site_list,
                search_term=search_term,
                location=country,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed=country,
                is_remote=is_remote,
            )
            jobs["search_country"] = country
            all_jobs.append(jobs)
            print(f"  -> {len(jobs)} jobs found in {country}")
        except Exception as e:
            print(f"  -> Failed for {country}: {e}")
            errors[country] = str(e)

    if not all_jobs:
        return {"total": 0, "jobs": [], "errors": errors}

    combined = pd.concat(all_jobs,ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"])

    # Replace NaN with None so it serializes as valid JSON (NaN isn't valid JSON)
    combined = combined.where(pd.notnull(combined), None)

    return {
        "total": len(combined),
        "jobs": combined.to_dict(orient="records"),
        "errors": errors,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)