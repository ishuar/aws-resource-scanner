"""
Cache module for AWS Scanner

Handles caching of scan results to improve performance and reduce API calls.
"""

import hashlib
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, cast

# Cache directory for scan results
CACHE_DIR = Path("/tmp/aws_scanner_cache")
CACHE_TTL_MINUTES = 10  # Cache TTL in minutes


def get_cache_key(
    region: str,
    service: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> str:
    """Generate a cache key for the given parameters."""
    cache_data = f"{region}:{service}:{tag_key or ''}:{tag_value or ''}"
    return hashlib.md5(cache_data.encode()).hexdigest()


def get_cached_result(
    region: str,
    service: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get cached result if available and not expired."""
    if not CACHE_DIR.exists():
        return None

    cache_key = get_cache_key(region, service, tag_key, tag_value)
    cache_file = CACHE_DIR / f"{cache_key}.pkl"

    if cache_file.exists():
        try:
            with open(cache_file, "rb") as f:
                cached_data = pickle.load(f)

            # Check if cache is still valid
            cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - cache_time < timedelta(minutes=CACHE_TTL_MINUTES):
                return cast(Dict[str, Any], cached_data)
        except Exception:
            pass  # Ignore cache read errors

    return None


def cache_result(
    region: str,
    service: str,
    result: Any,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> None:
    """Cache the scan result."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_key = get_cache_key(region, service, tag_key, tag_value)
        cache_file = CACHE_DIR / f"{cache_key}.pkl"

        with open(cache_file, "wb") as f:
            pickle.dump(result, f)
    except Exception:
        pass  # Ignore cache write errors
