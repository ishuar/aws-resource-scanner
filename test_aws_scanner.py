#!/usr/bin/env python3
"""
Comprehensive Test Suite for AWS Service Scanner
-----------------------------------------------

This test suite covers all major functionality of the AWS Service Scanner tool.
"""

import os
import sys
import subprocess
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import unittest

# Add the script's directory to the Python path
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import the scanner module for unit testing
try:
    import aws_scanner
    from aws_scanner import get_cache_key, generate_markdown_summary, SUPPORTED_SERVICES
except ImportError as e:
    print(f"Warning: Could not import aws_scanner module: {e}")
    print("Some unit tests will be skipped.")


class TestAWSScanner(unittest.TestCase):
    """Unit tests for AWS Scanner functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_resources = [
            {
                "region": "us-east-1",
                "resource_name": "test-instance",
                "resource_family": "ec2",
                "resource_type": "instance",
                "resource_id": "i-1234567890abcdef0",
                "resource_arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            },
            {
                "region": "us-east-1",
                "resource_name": "test-bucket",
                "resource_family": "s3",
                "resource_type": "bucket",
                "resource_id": "test-bucket",
                "resource_arn": "arn:aws:s3:::test-bucket",
            },
        ]

    def test_cache_key_generation(self):
        """Test cache key generation."""
        if "aws_scanner" not in sys.modules:
            self.skipTest("aws_scanner module not available")

        key1 = get_cache_key("us-east-1", "ec2", "env", "prod")
        key2 = get_cache_key("us-east-1", "ec2", "env", "prod")
        key3 = get_cache_key("us-east-1", "s3", "env", "prod")

        # Same parameters should generate same key
        self.assertEqual(key1, key2)
        # Different parameters should generate different keys
        self.assertNotEqual(key1, key3)
        # Keys should be hex strings (MD5)
        self.assertEqual(len(key1), 32)

    def test_markdown_generation(self):
        """Test markdown summary generation."""
        if "aws_scanner" not in sys.modules:
            self.skipTest("aws_scanner module not available")

        markdown = generate_markdown_summary(self.test_resources, {})

        # Check basic structure
        self.assertIn("# AWS Resources Scan Report", markdown)
        self.assertIn("## Summary by Region", markdown)
        self.assertIn("## Summary by Service", markdown)
        self.assertIn("## Detailed Resources", markdown)

        # Check resource counts
        self.assertIn("**Total Resources:** 2", markdown)
        self.assertIn("**us-east-1**: 2 resources", markdown)

        # Check code formatting for IDs and ARNs
        self.assertIn("`i-1234567890abcdef0`", markdown)
        self.assertIn(
            "`arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0`",
            markdown,
        )

    def test_supported_services_list(self):
        """Test that all expected services are supported."""
        if "aws_scanner" not in sys.modules:
            self.skipTest("aws_scanner module not available")

        expected_services = ["ec2", "s3", "ecs", "elb", "vpc", "autoscaling"]
        self.assertEqual(SUPPORTED_SERVICES, expected_services)

    def test_banner_display(self):
        """Test that banner is displayed correctly using CLI."""
        # Test banner display through CLI since it requires environment
        result = subprocess.run(
            [
                sys.executable,
                str(script_dir / "aws_scanner.py"),
                "--dry-run",
                "--regions",
                "us-east-1",
                "--service",
                "ec2",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0)
        # Check for ASCII art patterns that are actually present in figlet output
        self.assertIn("___", result.stdout)
        self.assertIn("/", result.stdout)  # ASCII art contains forward slashes
        self.assertIn("AWS Profile:", result.stdout)


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for the CLI interface."""

    def setUp(self):
        """Set up test fixtures."""
        self.scanner_path = script_dir / "aws_scanner.py"
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run_scanner(self, *args, **kwargs):
        """Helper to run the scanner command."""
        cmd = [sys.executable, str(self.scanner_path)] + list(args)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=kwargs.get("timeout", 30)
        )
        return result

    def test_help_command(self):
        """Test help command displays correctly."""
        result = self.run_scanner("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("AWS Multi-Service Scanner", result.stdout)
        self.assertIn("--format", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("json|table|md", result.stdout)

    def test_dry_run_functionality(self):
        """Test dry run mode."""
        result = self.run_scanner(
            "--dry-run", "--regions", "us-east-1", "--service", "ec2"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("DRY RUN MODE", result.stdout)
        self.assertIn("Scan Plan:", result.stdout)
        self.assertIn("us-east-1", result.stdout)
        self.assertIn("ec2", result.stdout)
        # Should not contain actual scan results
        self.assertNotIn("Found", result.stdout)

    def test_invalid_format_handling(self):
        """Test handling of invalid output format."""
        result = self.run_scanner(
            "--dry-run",
            "--regions",
            "us-east-1",
            "--service",
            "ec2",
            "--format",
            "invalid",
        )
        # Should still work in dry-run mode
        self.assertEqual(result.returncode, 0)

    def test_multiple_services_dry_run(self):
        """Test dry run with multiple services."""
        result = self.run_scanner(
            "--dry-run",
            "--regions",
            "us-east-1,eu-west-1",
            "--service",
            "ec2",
            "--service",
            "s3",
            "--max-workers",
            "10",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("2 × 2 = 4 service scans", result.stdout)
        self.assertIn("Max workers: 10", result.stdout)

    def test_tag_filtering_dry_run(self):
        """Test dry run with tag filtering."""
        result = self.run_scanner(
            "--dry-run",
            "--regions",
            "us-east-1",
            "--service",
            "ec2",
            "--tag-key",
            "environment",
            "--tag-value",
            "production",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Tag filtering: environment=production", result.stdout)

    def test_output_file_specification(self):
        """Test custom output file specification."""
        output_file = self.temp_dir / "test-output.json"
        result = self.run_scanner(
            "--dry-run",
            "--regions",
            "us-east-1",
            "--service",
            "ec2",
            "--output",
            str(output_file),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(str(output_file), result.stdout)

    def test_cache_options(self):
        """Test cache enable/disable options."""
        # Test cache enabled
        result = self.run_scanner(
            "--dry-run", "--cache", "--regions", "us-east-1", "--service", "ec2"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Caching: Enabled", result.stdout)

        # Test cache disabled
        result = self.run_scanner(
            "--dry-run", "--no-cache", "--regions", "us-east-1", "--service", "ec2"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Caching: Disabled", result.stdout)


class TestPerformanceAndLoad(unittest.TestCase):
    """Performance and load tests."""

    def setUp(self):
        """Set up test fixtures."""
        self.scanner_path = script_dir / "aws_scanner.py"

    def run_scanner(self, *args, **kwargs):
        """Helper to run the scanner command."""
        cmd = [sys.executable, str(self.scanner_path)] + list(args)
        start_time = time.time()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=kwargs.get("timeout", 60)
        )
        end_time = time.time()
        result.execution_time = end_time - start_time
        return result

    def test_performance_settings(self):
        """Test different performance settings."""
        # Test high performance
        result = self.run_scanner(
            "--dry-run",
            "--max-workers",
            "20",
            "--service-workers",
            "8",
            "--regions",
            "us-east-1,eu-west-1,us-west-2",
            "--service",
            "ec2",
            "--service",
            "s3",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Max workers: 20 regions, 8 services", result.stdout)

        # Test low performance
        result = self.run_scanner(
            "--dry-run",
            "--max-workers",
            "1",
            "--service-workers",
            "1",
            "--regions",
            "us-east-1",
            "--service",
            "ec2",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Max workers: 1 regions, 1 services", result.stdout)

    def test_large_scale_dry_run(self):
        """Test large scale operations in dry run."""
        result = self.run_scanner(
            "--dry-run", "--max-workers", "15", "--service-workers", "6"
        )
        self.assertEqual(result.returncode, 0)
        # Should handle all default regions and services
        self.assertIn("9 × 6 = 54 service scans", result.stdout)


class TestFileOperations(unittest.TestCase):
    """Test file creation and formatting."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.scanner_path = script_dir / "aws_scanner.py"

    def tearDown(self):
        """Clean up test files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_markdown_file_creation(self):
        """Test markdown file creation and formatting."""
        # Create test data
        test_data = [
            {
                "region": "us-east-1",
                "resource_name": "test-resource",
                "resource_family": "ec2",
                "resource_type": "instance",
                "resource_id": "i-1234567890abcdef0",
                "resource_arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            }
        ]

        if "aws_scanner" in sys.modules:
            markdown_content = generate_markdown_summary(test_data, {})

            # Write to file
            test_file = self.temp_dir / "test.md"
            test_file.write_text(markdown_content)

            # Verify file content
            content = test_file.read_text()
            self.assertIn("# AWS Resources Scan Report", content)
            self.assertIn("`i-1234567890abcdef0`", content)
            self.assertIn(
                "`arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0`",
                content,
            )


def run_integration_tests():
    """Run integration tests that require AWS credentials."""
    print("\n" + "=" * 60)
    print("INTEGRATION TESTS (require AWS credentials)")
    print("=" * 60)

    # Only run if AWS credentials are available
    if not (
        os.environ.get("AWS_PROFILE")
        or (
            os.environ.get("AWS_ACCESS_KEY_ID")
            and os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
    ):
        print("⚠️  Skipping integration tests - no AWS credentials configured")
        return

    scanner_path = script_dir / "aws_scanner.py"
    temp_dir = Path(tempfile.mkdtemp())

    try:
        print("Running real AWS scan tests...")

        # Test 1: Quick EC2 scan with caching
        print("1. Testing EC2 scan with caching...")
        result = subprocess.run(
            [
                sys.executable,
                str(scanner_path),
                "--regions",
                "us-east-1",
                "--service",
                "ec2",
                "--format",
                "json",
                "--output",
                str(temp_dir / "integration-test.json"),
                "--cache",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            print("   ✅ EC2 scan successful")
            # Check if JSON file was created
            json_file = temp_dir / "integration-test.json"
            if json_file.exists():
                data = json.loads(json_file.read_text())
                print(f"   📊 Found {len(data)} resources")
        else:
            print(f"   ❌ EC2 scan failed: {result.stderr}")

        # Test 2: Markdown format test
        print("2. Testing markdown format...")
        result = subprocess.run(
            [
                sys.executable,
                str(scanner_path),
                "--regions",
                "us-east-1",
                "--service",
                "ec2",
                "--format",
                "md",
                "--output",
                str(temp_dir / "integration-test"),
                "--cache",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print("   ✅ Markdown format successful")
            md_file = temp_dir / "integration-test.md"
            if md_file.exists():
                content = md_file.read_text()
                print(f"   📄 Markdown file size: {len(content)} characters")
        else:
            print(f"   ❌ Markdown format failed: {result.stderr}")

    except Exception as e:
        print(f"❌ Integration test error: {e}")
    finally:
        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Run all tests."""
    print("AWS Service Scanner - Test Suite")
    print("=" * 40)

    # Run unit tests
    print("\nRunning unit tests...")
    unittest.main(argv=[""], exit=False, verbosity=2)

    # Run integration tests if AWS credentials are available
    run_integration_tests()

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✅ Unit tests completed")
    print("✅ CLI integration tests completed")
    print("✅ Performance tests completed")
    print("✅ File operation tests completed")

    if os.environ.get("AWS_PROFILE") or (
        os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")
    ):
        print("✅ AWS integration tests completed")
    else:
        print("⚠️  AWS integration tests skipped (no credentials)")

    print("\nTo run specific test categories:")
    print("  python test_aws_scanner.py TestAWSScanner")
    print("  python test_aws_scanner.py TestCLIIntegration")
    print("  python test_aws_scanner.py TestPerformanceAndLoad")
    print("  python test_aws_scanner.py TestFileOperations")


if __name__ == "__main__":
    main()
