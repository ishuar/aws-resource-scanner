"""
AWS Scanner Library Package

This package contains modular components for the AWS Service Scanner tool.
"""

__version__ = "1.0.0"
__author__ = "ishuar"

# Import commonly used functions for convenience
from .cache import cache_result, get_cache_key, get_cached_result
from .outputs import compare_with_existing, generate_markdown_summary, output_results
from .scan import scan_region, scan_service

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
