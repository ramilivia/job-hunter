# JobDrop API

A small, standalone FastAPI service that exposes **Wellfound** (formerly
AngelList) and **Adzuna** job listings over HTTP, backed by the
[`jobdrop`](https://github.com/kbwhodat/jobdrop) scraper library.

## Why a separate project?

The existing `jobs_api` in the `JobSpy` repo runs **JobSpy** exactly as its name
suggests. JobSpy and JobDrop cannot live in the same Python environment:

| Library | `curl_cffi` constraint |
|---|---|
| `python-jobspy` 1.4.1 | `curl_cffi>=0.16.2` |
| `jobdrop` 2.10.0     | `curl-cffi<0.8.0,>=0.7.0` |

`pip` cannot resolve both, so this project keeps JobDrop in its own virtualenv,
exposing its own HTTP endpoint on a different port (8001) from the JobSpy API
(8000).

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

## Endpoints

### `GET /wellfound`

Scrapes Wellfound (formerly AngelList) via Camoufox. Query parameters:

| Param            | Default                                    | Description |
|---|---|---|
| `positions`      | `Solutions Architect,Engineering Manager,Forward Deployed Engineer` | Comma-separated job titles, searched one at a time |
| `countries`      | `Netherlands,Germany,Poland,Spain,Portugal,Estonia,Czechia,Switzerland,Austria,Norway,Denmark,Sweden,France` | Comma-separated countries (or free-text locations), cross-joined with each position |
| `results_wanted` | `20`                                       | Max results per position × country |
| `hours_old`      | `none`                                     | Drop postings older than N hours (omit to return all postings regardless of age) |
| `is_remote`      | `false`                                    | Remote-only roles |
| `max_workers`    | `3`                                        | Concurrent scrapes (Wellfound renders slowly; keep low) |

### `GET /builtin`

Scrapes Built In (builtin.com) via jobdrop's plain-HTML scraper (no Camoufox,
sub-second per call). Built In is a tech-vetted local job board family (NYC,
LA, Chicago, Atlanta, etc.); jobdrop cross-source dedups its results against
LinkedIn/Indeed by (company, title), so Built In contributes its tech-quality
filter without inflating result counts.

Country filtering works by mapping each configured country to its ISO alpha-3
code (`code_alpha3` in `shared_config.json`) and passing it as Built In's
`country=` query param, plus the `/jobs/remote` path segment for remote-only
results. Built In ignores the plain `location=` param that jobdrop's stock
scraper emits, so this route applies a small URL-builder patch to make the
filter actually take effect.

| Param            | Default                                    | Description |
|---|---|---|
| `positions`      | `Solutions Architect,Engineering Manager,Forward Deployed Engineer` | Comma-separated job titles, searched one at a time |
| `countries`      | (from shared config)                       | Comma-separated countries (or free-text locations), cross-joined with each position |
| `results_wanted` | `20`                                       | Max results per position × country |
| `hours_old`      | `24` (from shared config)                  | Drop postings older than N hours |
| `is_remote`      | `false`                                    | Remote-only roles |
| `max_workers`    | `4`                                        | Concurrent requests |

### `GET /adzuna`

Queries Adzuna via jobdrop's plain-HTTP scraper (sub-second per call, no
Camoufox). Credentials come from the `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` env
vars, falling back to jobdrop's bundled defaults when absent.

| Param            | Default                                    | Description |
|---|---|---|
| `positions`      | `Solutions Architect,Engineering Manager,Forward Deployed Engineer` | Comma-separated job titles, searched one at a time |
| `countries`      | (from shared config)                       | Comma-separated countries, cross-joined with each position |
| `results_wanted` | `20`                                       | Max results per position × country |
| `hours_old`      | `24` (from shared config)                  | Drop postings older than N hours |
| `is_remote`      | `false`                                    | Remote-only roles |
| `max_workers`    | `4`                                        | Concurrent requests |

> **Country caveat**: jobdrop maps country names to Adzuna's 2-letter code via
> a fixed map. The route rejects unsupported countries up front and reports them
> in `errors` (e.g. Portugal, Estonia, Czechia, Norway, Denmark, Sweden). The
> supported European set is Germany, France, Netherlands, Poland, Spain,
> Switzerland, Austria.

Examples:

```bash
curl "http://localhost:8001/wellfound?positions=Engineering%20Manager&countries=Germany%2CNetherlands&hours_old=168"
curl "http://localhost:8001/builtin?positions=Engineering%20Manager&countries=Germany%2CNetherlands"
curl "http://localhost:8001/adzuna?positions=Engineering%20Manager&countries=Germany%2CNetherlands"
curl "http://localhost:8001/adzuna?positions=Solutions%20Architect&countries=Germany&hours_old=24"
```

Response shape (matches the JobSpy `jobs_api` so the same pipeline can consume
both):

```json
{
  "total": 3,
  "jobs": [
    {
      "id": "...",
      "site": "adzuna",
      "job_url": "https://www.adzuna.co.uk/...",
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
│   ├── adzuna_routes.py     # GET /adzuna endpoint + scraping logic
│   ├── builtin_routes.py    # GET /builtin endpoint + scraping logic
│   ├── common.py            # JSON-safe serialization helpers
│   └── config.py            # default positions / hours / limit
└── requirements.txt