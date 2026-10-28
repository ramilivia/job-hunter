"""Shared search defaults, loaded from the shared_config.json at the common
parent (the same file the JobSpy jobs_api reads)."""

import json
import os
from pathlib import Path

# Env var lets Docker mount the file anywhere (e.g. /config/shared_config.json);
# otherwise we walk up the directory tree to find it (handles the nested
# JobSpy/JobSpy and JobSpy/JobDrop checkout layout).
_HERE = Path(__file__).resolve()
_SHARED_CONFIG_ENV = "SHARED_CONFIG_PATH"

# Fallback values are kept in sync with shared_config.json so the service still
# starts if the shared file is missing or unreadable.
_FALLBACK_POSITIONS = [
    "Solutions Architect",
    "Engineering Manager",
    "Forward Deployed Engineer",
]
_FALLBACK_COUNTRIES = [
    {"name": "Netherlands", "code": "nl"},
    {"name": "Germany", "code": "de"},
    {"name": "Poland", "code": "pl"},
    {"name": "Spain", "code": "es"},
    {"name": "Portugal", "code": "pt"},
    {"name": "Estonia", "code": "ee"},
    {"name": "Czechia", "code": "cz"},
    {"name": "Switzerland", "code": "ch"},
    {"name": "Austria", "code": "at"},
    {"name": "Norway", "code": "no"},
    {"name": "Denmark", "code": "dk"},
    {"name": "Sweden", "code": "se"},
    {"name": "France", "code": "fr"},
]


def _resolve_shared_config_path() -> Path:
    env_path = os.environ.get(_SHARED_CONFIG_ENV)
    if env_path:
        return Path(env_path)

    current = _HERE.parent
    for _ in range(6):
        candidate = current / "shared_config.json"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return Path("shared_config.json")


def _load_shared_config() -> dict:
    path = _resolve_shared_config_path()
    data: dict = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    return data


_CONFIG = _load_shared_config()

DEFAULT_POSITIONS = _CONFIG.get("positions") or _FALLBACK_POSITIONS

_countries = _CONFIG.get("countries") or _FALLBACK_COUNTRIES
# Wellfound geocodes from a free-text location, so we pass it the country
# name (not the ISO code). Kept in the same order as the shared file.
DEFAULT_COUNTRY_NAMES = [c["name"] for c in _countries]

DEFAULT_HOURS = _CONFIG.get("hours_old") or 24
DEFAULT_LIMIT = 20

# Wellfound postings are sparse and often days/weeks old, so a 24h recency
# filter would silently drop almost every result. Default to "no recency
# filter" (None) so a plain /wellfound call returns all matching jobs.
WELLFOUND_DEFAULT_HOURS = DEFAULT_HOURS
