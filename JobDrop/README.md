# JobDrop Wellfound API

A small, standalone FastAPI service that exposes **Wellfound** (formerly
AngelList) job listings over HTTP, backed by the
[`jobdrop`](https://github.com/kbwhodat/jobdrop) scraper library.

## Why a separate project?

The existing `jobs_api` in the `JobSpy` repo runs **JobSpy** exactly as its name
suggests. JobSpy and JobDrop cannot live in the same Python environment:

| Library | `curl_cffi` constraint |
|---|---|
| `python-jobspy` 1.4.1 | `curl_cffi>=0.16.2` |
| `jobdrop` 2.10.0     | `curl-cffi<0.8.0,>=0.7.0` |

`pip` cannot resolve both, so this project keeps JobDrop (and its Wellfound
scraper) in its own virtualenv, exposing its own HTTP endpoint on a different
port (8001) from the JobSpy API (8000).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> The first Wellfound request downloads a patched Firefox (~300MB) into
> `~/.cache/camoufox/` so it can pass Wellfound's DataDome WAF. It can take
> ~30s on a fast connection; subsequent requests are much faster.

## Run

```bash
python3 -m app        # serves on http://0.0.0.0:8001
```

## Endpoint

```
GET /wellfound
```

Query parameters:

| Param            | Default                                    | Description |
|---|---|---|
| `positions`      | `Solutions Architect,Engineering Manager,Forward Deployed Engineer` | Comma-separated job titles, searched one at a time |
| `countries`      | `Netherlands,Germany,Poland,Spain,Portugal,Estonia,Czechia,Switzerland,Austria,Norway,Denmark,Sweden,France` | Comma-separated countries (or free-text locations), cross-joined with each position |
| `results_wanted` | `20`                                       | Max results per position × country |
| `hours_old`      | `none`                                     | Drop postings older than N hours (omit to return all postings regardless of age) |
| `is_remote`      | `false`                                    | Remote-only roles |
| `max_workers`    | `1`                                        | Concurrent scrapes (Wellfound renders slowly; keep low) |

Examples:

```bash
curl "http://localhost:8001/wellfound?positions=Engineering%20Manager&countries=Germany%2CNetherlands&hours_old=168"
curl "http://localhost:8001/wellfound?positions=Data%20Engineer,Backend%20Engineer&countries=Berlin%2CAmsterdam"
```

Response shape (matches the JobSpy `jobs_api` so the same pipeline can consume
both):

```json
{
  "total": 3,
  "jobs": [
    {
      "id": "...",
      "site": "wellfound",
      "job_url": "https://wellfound.com/jobs/...",
      "title": "Engineering Manager",
      "company": "Acme",
      "location": "Berlin, Germany",
      "date_posted": "2026-10-27",
      "job_type": ["fulltime"],
      "interval": "yearly",
      "min_amount": 120000,
      "max_amount": 160000,
      "currency": "USD",
      "is_remote": true,
      "description": "...",
      "company_url": "https://wellfound.com/company/acme",
      "company_logo": "..."
    }
  ],
  "errors": {}
}
```

## Project layout

```
JobDrop/
├── app/
│   ├── __init__.py          # FastAPI app factory + router registration
│   ├── __main__.py          # uvicorn entrypoint (port 8001)
│   ├── wellfound_routes.py  # GET /wellfound endpoint + scraping logic
│   ├── common.py            # JSON-safe serialization helpers
│   └── config.py            # default positions / hours / limit
└── requirements.txt