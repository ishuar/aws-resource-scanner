#!/usr/bin/env python3
"""
Entry point wrapper for aws-scanner command line tool.
"""

import sys
from pathlib import Path

# Import and run the main app
from aws_scanner import app

# Add the package directory to Python path
package_dir = Path(__file__).parent.absolute()
if str(package_dir) not in sys.path:
    sys.path.insert(0, str(package_dir))

if __name__ == "__main__":
    app()
