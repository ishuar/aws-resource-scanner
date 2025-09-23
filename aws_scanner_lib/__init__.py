"""
AWS Scanner Library Package

This package contains modular components for the AWS Service Scanner tool.
"""

__version__ = "1.0.0"
__author__ = "AWS Scanner Team"

# Import commonly used functions for convenience
from .cache import get_cache_key, get_cached_result, cache_result
from .scan import scan_service, scan_region
from .outputs import generate_markdown_summary, output_results, compare_with_existing

__all__ = [
    "get_cache_key",
    "get_cached_result",
    "cache_result",
    "scan_service",
    "scan_region",
    "generate_markdown_summary",
    "output_results",
    "compare_with_existing",
]
