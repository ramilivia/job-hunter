import json
import math

import requests
from fastapi.encoders import jsonable_encoder
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class BackoffRetry(Retry):
    """urllib3 skips the wait before the first retry, which is useless after a 429."""

    def get_backoff_time(self) -> float:
        attempts = len(self.history)
        if attempts == 0:
            return 0
        return float(min(self.backoff_max, self.backoff_factor * 2 ** (attempts - 1)))


def retrying_session() -> requests.Session:
    """Session that retries 429/5xx, honouring Retry-After, else waiting 5s, 10s, 20s."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=BackoffRetry(
        total=3,
        backoff_factor=5,
        status_forcelist=[429, 500, 502, 503, 504],
    ))
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def clean_nans(obj):
    """Recursively replace NaN, Infinity, and -Infinity with None for JSON safety."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(v) for v in obj]
    return obj


def json_safe_jobs(records: list, errors: dict) -> list:
    """Convert each job to JSON-safe data, skipping (and recording) any job that can't be, so one bad job never fails the whole response."""
    safe_jobs = []
    for index, record in enumerate(records):
        try:
            job = jsonable_encoder(clean_nans(record))
            json.dumps(job, allow_nan=False)
            safe_jobs.append(job)
        except Exception as e:
            label = f"job #{index}"
            if isinstance(record, dict):
                label = record.get("job_url") or record.get("url") or label
            errors[f"skipped job | {label}"] = str(e)
    return safe_jobs
