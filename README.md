# Job Hunter

Two job-search services running side by side:

| Service  | Project  | Library | Port | Endpoint(s) |
|---|---|---|---|---|
| `jobspy`  | `JobSpy/` | [JobSpy](https://github.com/speedyapply/JobSpy)  | 8000 | `/linkedin`, `/indeed`, `/google`, `/glassdoor`, `/freehire`, `/arbeitnow` |
| `jobdrop` | `JobDrop/` | [JobDrop](https://github.com/kbwhodat/jobdrop) | 8001 | `/wellfound`, `/adzuna` |

They are intentionally separate projects because **JobSpy and JobDrop pin
incompatible versions of `curl_cffi`** and cannot run in the same Python
environment. Docker Compose isolates each one in its own container.

## One global config

Both services read the same file: [`shared_config.json`](./shared_config.json).

```json
{
  "positions": ["Solutions Architect", "Engineering Manager", "Forward Deployed Engineer"],
  "countries": [
    { "name": "Netherlands", "code": "nl" },
    { "name": "Germany", "code": "de" }
  ],
  "hours_old": 24
}
```

- **`positions`** → used by both `jobspy` and `jobdrop` routes as the default
  comma-separated `positions` query parameter.
- **`countries`** → used by `jobspy` (LinkedIn/Indeed use `name`, Freehire uses
  `code`). Wellfound geocodes from a free-text location, so it doesn't need it.
- **`hours_old`** → default recency filter (hours) for both services. Wellfound
  overrides this to `none` because its sparse postings would otherwise be
  dropped almost entirely.

Edit `shared_config.json` to change defaults everywhere. Each service resolves
the file via the `SHARED_CONFIG_PATH` env var, falling back to walking up the
directory tree to find a sibling `shared_config.json`.

## Run with Docker Compose

```bash
docker compose up --build
```

| URL | Service |
|---|---|
| http://localhost:8000/linkedin | JobSpy |
| http://localhost:8000/indeed   | JobSpy |
| http://localhost:8001/wellfound | JobDrop (Wellfound) |
| http://localhost:8001/adzuna    | JobDrop (Adzuna)    |

The shared config is bind-mounted read-only into both containers at
`/config/shared_config.json`.

> **Wellfound first run**: JobDrop downloads a patched Firefox (~300MB) into a
> named volume (`camoufox_cache`) to pass Wellfound's DataDome WAF. The first
> request is slow (~30s); subsequent requests reuse it.

## Run without Docker

Each project has its own setup (see its own `README.md`):

```bash
# JobSpy
cd JobSpy
python3 -m venv venv && source venv/bin/activate
pip install fastapi uvicorn requests
python3 -m jobs_api                      # port 8000

# JobDrop
cd JobDrop
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 -m app                           # port 8001
```

Both will auto-discover `shared_config.json` when run from this checkout layout.

## Layout

```
.
├── shared_config.json    # global titles + countries (both services read this)
├── docker-compose.yml    # runs jobspy + jobdrop together
├── JobSpy/
│   ├── jobs_api/         # JobSpy FastAPI wrapper
│   ├── jobspy/           # JobSpy library
│   ├── pyproject.toml
│   └── Dockerfile
└── JobDrop/
    ├── app/              # JobDrop Wellfound FastAPI wrapper
    ├── requirements.txt
    ├── Dockerfile
    └── README.md