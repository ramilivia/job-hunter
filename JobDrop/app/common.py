import json
import math

from fastapi.encoders import jsonable_encoder


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