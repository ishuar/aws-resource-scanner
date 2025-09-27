#!/usr/bin/env python3
"""
Test script to verify AWS Scanner installation and basic functionality.
"""

import subprocess
import sys
from pathlib import Path


def test_installation():
    """Test if aws-scanner command is available."""
    try:
        result = subprocess.run(
            ["aws-scanner", "--help"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ aws-scanner command is available")
            return True
        else:
            print("❌ aws-scanner command failed")
            print(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ aws-scanner command not found")
        print("Please install the package first:")
        print("  pip install -e .")
        return False
    except subprocess.TimeoutExpired:
        print("❌ aws-scanner command timed out")
        return False


def test_imports():
    """Test if all required modules can be imported."""
    try:
        # Test the script's directory structure
        script_dir = Path(__file__).parent
        services_dir = script_dir / "services"

        if not services_dir.exists():
            print("❌ services directory not found")
            return False

        # Test if we can import the main module
        sys.path.insert(0, str(script_dir))
        import aws_scanner

        print("✅ aws_scanner module imports successfully")

        # Test services imports
        from services import process_ec2_output, scan_ec2

        print("✅ services modules import successfully")

        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install boto3 botocore typer rich deepdiff")
        return False


def main():
    """Run all tests."""
    print("Testing AWS Scanner installation...\n")

    tests = [
        ("Module imports", test_imports),
        ("Command availability", test_installation),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        if test_func():
            passed += 1
        print()

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! The tool is ready to use.")
        print("\nTry running:")
        print("  aws-scanner --help")
    else:
        print("❌ Some tests failed. Please check the installation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
