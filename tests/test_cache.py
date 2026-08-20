"""
Cache seam: aws_scanner_lib.cache

The interface every scan path relies on: get_cache_key / cache_result /
get_cached_result. Planned refactors must keep keys stable (a changed key
format silently invalidates every user's warm cache) and keep the
store→retrieve round-trip lossless.
"""

from datetime import datetime, timedelta
from pathlib import Path

from aws_scanner_lib.cache import cache_result, get_cache_key, get_cached_result

REGION = "eu-central-1"


class TestCacheKey:
    def test_key_is_stable_across_versions(self) -> None:
        # Known-good literals: md5("eu-central-1:ec2::") and
        # md5("eu-central-1:ec2:env:prod"). If this test fails the key
        # format changed and every existing cache entry is invalidated —
        # that must be a deliberate decision, not a refactor side effect.
        assert get_cache_key(REGION, "ec2") == "d02463c473244acc460d09c4b6c28e99"
        assert (
            get_cache_key(REGION, "ec2", "env", "prod")
            == "928e52ecd1ebf3bddfe695b8deaefe19"
        )

    def test_tags_participate_in_the_key(self) -> None:
        base = get_cache_key(REGION, "ec2")
        assert get_cache_key(REGION, "ec2", "env") != base
        assert get_cache_key(REGION, "ec2", None, "prod") != base
        assert get_cache_key(REGION, "ec2", "env", "prod") != get_cache_key(
            REGION, "ec2", "env"
        )

    def test_region_and_service_participate_in_the_key(self) -> None:
        assert get_cache_key(REGION, "ec2") != get_cache_key("us-east-1", "ec2")
        assert get_cache_key(REGION, "ec2") != get_cache_key(REGION, "s3")


class TestCacheRoundTrip:
    def test_miss_when_nothing_stored(self) -> None:
        assert get_cached_result(REGION, "ec2") is None

    def test_store_then_retrieve_is_lossless(self) -> None:
        payload = {"instances": [{"InstanceId": "i-123"}], "volumes": []}
        cache_result(REGION, "ec2", payload)
        assert get_cached_result(REGION, "ec2") == payload

    def test_entries_are_isolated_by_tags(self) -> None:
        cache_result(REGION, "ec2", {"instances": ["untagged"]})
        cache_result(REGION, "ec2", {"instances": ["tagged"]}, "env", "prod")
        assert get_cached_result(REGION, "ec2") == {"instances": ["untagged"]}
        assert get_cached_result(REGION, "ec2", "env", "prod") == {
            "instances": ["tagged"]
        }

    def test_expired_entry_is_a_miss(self, isolated_cache: Path) -> None:
        import os

        cache_result(REGION, "ec2", {"instances": []})
        # Age the cache file past the 10-minute TTL via its mtime,
        # which is what the TTL check reads.
        cache_file = next(isolated_cache.glob("*.pkl"))
        expired = datetime.now() - timedelta(minutes=11)
        os.utime(cache_file, (expired.timestamp(), expired.timestamp()))

        assert get_cached_result(REGION, "ec2") is None

    def test_corrupt_entry_is_a_miss_not_a_crash(self, isolated_cache: Path) -> None:
        cache_result(REGION, "ec2", {"instances": []})
        cache_file = next(isolated_cache.glob("*.pkl"))
        cache_file.write_bytes(b"not a pickle")

        assert get_cached_result(REGION, "ec2") is None
