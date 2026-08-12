import pandas as pd
from jobspy import scrape_jobs

search_term = '"engineering manager" OR "solution architect" OR "staff engineer"'

countries = ["Germany", "Netherlands", "Spain", "Ireland", "Austria", "Sweden", "Denmark", "Norway", "Poland"]

all_jobs = []

for country in countries:
    print(f"Scraping {country}...")
    try:
        jobs = scrape_jobs(
            site_name=["indeed", "linkedin"],
            search_term=search_term,
            location=country,
            results_wanted=30,
            hours_old=168,          # last 7 days
            country_indeed=country,
            is_remote=False,
        )
        jobs["search_country"] = country
        all_jobs.append(jobs)
    except Exception as e:
        print(f"  Failed for {country}: {e}")

combined = pd.concat(all_jobs, ignore_index=True)
combined = combined.drop_duplicates(subset=["job_url"])

print(f"Total jobs found: {len(combined)}")

combined.to_json("jobs.json", orient="records", indent=2)