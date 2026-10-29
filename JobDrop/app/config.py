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
    {"name": "Netherlands", "code": "nl", "code_alpha3": "NLD"},
    {"name": "Germany", "code": "de", "code_alpha3": "DEU"},
    {"name": "Poland", "code": "pl", "code_alpha3": "POL"},
    {"name": "Spain", "code": "es", "code_alpha3": "ESP"},
    {"name": "Portugal", "code": "pt", "code_alpha3": "PRT"},
    {"name": "Estonia", "code": "ee", "code_alpha3": "EST"},
    {"name": "Czechia", "code": "cz", "code_alpha3": "CZE"},
    {"name": "Switzerland", "code": "ch", "code_alpha3": "CHE"},
    {"name": "Austria", "code": "at", "code_alpha3": "AUT"},
    {"name": "Norway", "code": "no", "code_alpha3": "NOR"},
    {"name": "Denmark", "code": "dk", "code_alpha3": "DNK"},
    {"name": "Sweden", "code": "se", "code_alpha3": "SWE"},
    {"name": "France", "code": "fr", "code_alpha3": "FRA"},
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

# Built In (builtin.com) filters by ISO alpha-3 country code rather than the
# alpha-2 ``code`` or the full name. Build a lookup keyed by both the free-text
# name and the alpha-2 code so either maps to the right Built In filter value.
COUNTRY_ALPHA3_LOOKUP: dict[str, str] = {}
for _c in _countries:
    _alpha3 = _c.get("code_alpha3")
    if not _alpha3:
        continue
    COUNTRY_ALPHA3_LOOKUP[_c["name"].strip().lower()] = _alpha3
    if _c.get("code"):
        COUNTRY_ALPHA3_LOOKUP[_c["code"].strip().lower()] = _alpha3

DEFAULT_HOURS = _CONFIG.get("hours_old") or 24
DEFAULT_LIMIT = 20

# Wellfound postings are sparse and often days/weeks old, so a 24h recency
# filter would silently drop almost every result. Default to "no recency
# filter" (None) so a plain /wellfound call returns all matching jobs.
WELLFOUND_DEFAULT_HOURS = DEFAULT_HOURS
