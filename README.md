# AWS Resource Scanner

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive AWS multi-service scanner with tag-based filtering, parallel processing, and advanced optimization features. This tool enables efficient discovery and analysis of AWS resources across multiple regions and services with intelligent caching and rich output formats.

## ✨ Features

### 🔍 **Core Scanning Capabilities**
- **Multi-Service Support**: Scan EC2, S3, ECS, VPC, Auto Scaling Groups, and ELB resources
- **Multi-Region Scanning**: Concurrent scanning across multiple AWS regions
- **Tag-Based Filtering**: Filter resources by specific tag keys and values
- **Parallel Processing**: Optimized concurrent scanning for faster results
- **Intelligent Caching**: Built-in caching with TTL for improved performance

### 📊 **Output & Formatting**
- **Multiple Output Formats**: Table (default), JSON, and Markdown formats
- **Rich Console Output**: Beautiful, color-coded terminal output with progress indicators
- **File Export**: Save results to files for further processing
- **Structured Data**: Well-organized output for both human and machine consumption

### ⚙️ **Advanced Configuration**
- **Flexible Service Selection**: Choose specific services to scan
- **Region Customization**: Scan specific regions or use default region sets
- **Worker Configuration**: Configurable parallel workers for optimal performance
- **Dry Run Mode**: Preview scan operations without execution
- **Cache Management**: Enable/disable caching as needed

### 🛡️ **Reliability & Performance**
- **Error Handling**: Robust error handling with detailed logging
- **Progress Tracking**: Real-time progress indicators for long-running scans
- **Memory Optimization**: Efficient memory usage for large-scale scans
- **Graceful Degradation**: Continues operation even if some services fail

## 🏗️ **Supported AWS Services**

| Service | Description | Resources Scanned |
|---------|-------------|------------------|
| **EC2** | Elastic Compute Cloud | Instances, Security Groups, Key Pairs |
| **S3** | Simple Storage Service | Buckets and their configurations |
| **ECS** | Elastic Container Service | Clusters, Services, Tasks |
| **VPC** | Virtual Private Cloud | VPCs, Subnets, Route Tables, Internet Gateways |
| **Auto Scaling** | Auto Scaling Groups | ASGs and their configurations |
| **ELB** | Elastic Load Balancing | Application Load Balancers, Network Load Balancers |

## 📋 **Prerequisites**

Before installing the AWS Resource Scanner, ensure you have the following dependencies:

### Required Software
- **Python 3.10+** - Runtime environment
- **Poetry** - Python dependency management and packaging
- **pip** - Python package installer
- **AWS CLI** - AWS command line interface for authentication
- **pre-commit** - Git hooks framework (for development)

### AWS Configuration
- Valid AWS credentials configured via:
  - AWS SSO (`aws sso login`)
  - AWS CLI (`aws configure`)
  - Environment variables
  - IAM roles (for EC2/containers)

## 🚀 **Installation**

### Automated Setup (Recommended)

The easiest way to get started is using our automated setup script:

```bash
# Clone the repository
git clone https://github.com/ishuar/aws-resource-scanner.git
cd aws-resource-scanner

# Run the automated setup script
./setup.sh
```

The setup script will:
1. ✅ Check and install Python 3.10+
2. ✅ Install Poetry (Python dependency manager)
3. ✅ Install pre-commit (Git hooks framework)
4. ✅ Set up pre-commit hooks
5. ✅ Install all project dependencies via Poetry
6. ✅ Run verification tests
7. ✅ Install AWS CLI (if not present)
8. ✅ Provide AWS configuration guidance

For detailed setup instructions and troubleshooting, see [setup.sh](setup.sh).

### Manual Installation

If you prefer manual installation:

```bash
# Install dependencies (macOS with Homebrew)
brew install python3 poetry pre-commit awscli

# Install project dependencies
poetry install

# Set up pre-commit hooks
pre-commit install --install-hooks

# Verify installation
./run_quick_tests.sh
```

## 💻 **Usage**

### Basic Commands

```bash
# Display help and available commands
poetry run aws-scanner --help

# Display scan command help and options
poetry run aws-scanner scan --help

# Basic scan with default settings (all supported services, EU & US regions)
poetry run aws-scanner scan --regions us-east-1,eu-west-1,eu-central-1,us-west-2

# Scan specific services
poetry run aws-scanner scan --service ec2

# Scan specific regions
poetry run aws-scanner scan --regions us-east-1,eu-west-1
```

### Service-Specific Scanning

```bash
# Scan only EC2 resources
poetry run aws-scanner scan --service ec2

# Scan ECS and VPC resources
poetry run aws-scanner scan --service ecs

# Scan all services in specific regions
poetry run aws-scanner scan --regions us-east-1,us-west-2

# Combine service and region filtering
poetry run aws-scanner scan --service ec2 --regions eu-central-1,eu-west-1
```

### Tag-Based Filtering

```bash
# Filter by environment tag
poetry run aws-scanner scan --tag-key Environment --tag-value Production

# Filter by application tag
poetry run aws-scanner scan --tag-key app --tag-value web-server

# Filter by cost center in specific regions
poetry run aws-scanner scan --regions us-east-1 --tag-key CostCenter --tag-value Engineering
```

### Output Formats

```bash
# Default table format (human-readable)
poetry run aws-scanner scan --format table

# JSON format for programmatic processing
poetry run aws-scanner scan --format json --output results.json

# Markdown format for documentation
poetry run aws-scanner scan --format md --output report.md

# Export filtered results to JSON
poetry run aws-scanner scan --tag-key Environment --tag-value Production --format json --output prod-resources.json
```

### Advanced Options

```bash
# Dry run (preview without execution)
poetry run aws-scanner scan --dry-run --service ec2

# Disable caching for fresh data
poetry run aws-scanner scan --no-cache

# Configure worker threads for performance
poetry run aws-scanner scan --max-workers 10 --service-workers 6

# Compare with existing results
poetry run aws-scanner scan --compare --output current-scan.json
```

### Real-World Examples

```bash
# Production infrastructure audit
poetry run aws-scanner scan \
    --tag-key Environment --tag-value Production \
    --format json --output production-audit.json

# Regional compliance check
poetry run aws-scanner scan \
    --regions eu-west-1,eu-central-1 \
    --service ec2 \
    --format md --output eu-compliance-report.md

# Application-specific resource inventory
poetry run aws-scanner scan \
    --tag-key Application --tag-value MyApp \
    --format table

# Development environment scan
poetry run aws-scanner scan \
    --regions us-west-2 \
    --tag-key Environment --tag-value Development \
    --no-cache
```

## 🔧 **Configuration**

### AWS Profile Configuration

```bash
# Set AWS profile
export AWS_PROFILE=your-profile-name

# Login via SSO
aws sso login --profile $AWS_PROFILE

# Verify credentials
aws sts get-caller-identity
```

### Performance Tuning

- **Max Workers**: Adjust `--max-workers` (1-20) for region-level parallelism
- **Service Workers**: Adjust `--service-workers` (1-10) for service-level parallelism
- **Caching**: Use `--cache` for faster subsequent scans, `--no-cache` for fresh data

## 📁 **Project Structure**

```
aws-resource-scanner/
├── aws_scanner.py               # AWS main entrypoint.
├── cli.py                       # Main CLI application
├── setup.sh                     # Automated setup script
├── run_quick_tests.sh           # Test verification script
├── pyproject.toml               # Project configuration
├── services/                    # Service-specific scanners
│   ├── ec2_service.py           # EC2 resource scanner
│   ├── s3_service.py            # S3 resource scanner
│   ├── ecs_service.py           # ECS resource scanner
│   ├── vpc_service.py           # VPC resource scanner
│   ├── autoscaling_service.py   # Auto Scaling scanner
│   └── elb_service.py           # Load Balancer scanner
├── aws_scanner_lib/             # Core library modules
│   ├── cache.py                 # Caching functionality
│   ├── outputs.py               # Output formatting
│   ├── resource_groups_utils.py # resourceGroupTaggingApi scan when tags are used
│   └── scan.py                  # Core scanning logic
└── tests/                       # Test suite
```

## 🧪 **Testing**

```bash
# Run all tests
./run_quick_tests.sh

# Run specific test files
poetry run python -m pytest tests/test_aws_scanner.py

# Run with coverage
poetry run python -m pytest --cov=aws_scanner_lib tests/
```

## 🐛 **Troubleshooting**

### Common Issues

1. **AWS Credentials**: Ensure AWS credentials are properly configured
   ```bash
   aws sts get-caller-identity
   ```

2. **Python Version**: Verify Python 3.10+ is installed
   ```bash
   python3 --version
   ```

3. **Dependencies**: Reinstall dependencies if needed
   ```bash
   poetry install --no-cache
   ```

4. **Permissions**: Ensure your AWS user/role has necessary permissions for the services you're scanning

### Debug Mode

For detailed debugging information:

```bash
# Check logs (created during scans)
ls /tmp/aws_resource_scanner/

# Dry run to verify configuration
poetry run aws-scanner --dry-run
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install development dependencies: `poetry install`
4. Set up pre-commit hooks: `pre-commit install --install-hooks`
5. Make your changes and run tests: `./run_quick_tests.sh`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

## 📝 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- Built with [Typer](https://typer.tiangolo.com/) for CLI interface
- Styled with [Rich](https://rich.readthedocs.io/) for beautiful console output
- Powered by [Boto3](https://boto3.amazonaws.com/) for AWS integration
- Managed with [Poetry](https://python-poetry.org/) for dependency management

---

**Made with ❤️ for the AWS community**
