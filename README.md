# AWS Resource Scanner

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/ishuar/aws-resource-scanner/main.svg)](https://results.pre-commit.ci/latest/github/ishuar/aws-resource-scanner/main)

A comprehensive AWS multi-service scanner with tag-based filtering, parallel processing, advanced logging capabilities, and optimization features. This tool enables efficient discovery and analysis of AWS resources across multiple regions and services with intelligent caching, rich output formats, and detailed AWS API tracing.

## ✨ Features

### 🔍 Core Scanning Capabilities
- **Tag-Based Scan**: Scan resources by specific tag keys and values across all AWS services.
- **Multi-Service Support**: Scan EC2, S3, ECS, VPC, Auto Scaling Groups, and ELB resources with and without tags filters across all regions.
- **Multi-Region Scanning**: Concurrent scanning across multiple AWS regions
- **Parallel Processing**: Optimized concurrent scanning for faster results
- **Intelligent Caching**: Built-in caching with TTL for improved performance

### 📊 Output & Formatting
- **Multiple Output Formats**: Table (default), JSON, and Markdown formats
- **Rich Console Output**: Beautiful, color-coded terminal output with progress indicators
- **File Export**: Save results to files for further processing
- **Structured Data**: Well-organized output for both human and machine consumption

### 🔍 Advanced Logging & Debugging
- **Comprehensive Logging System**: Unified logging architecture with multiple output streams ([Logging Architecture](docs/LOGGING_ARCHITECTURE.md))
- **Debug Mode**: Detailed execution traces with `--debug` flag
- **AWS API Tracing**: Verbose boto3/botocore logging with `--verbose` flag
- **Custom Log Files**: Configurable log file paths with `--log-file`
- **Progress Isolation**: Separated console streams for logs vs progress displays
- **Rich Error Display**: Enhanced error formatting with caller context

### ⚙️ Advanced Configuration
- **Service Selection without Tags**: Choose specific services to scan. Currently supported [`ec2`, `vpc` , `elb`, `autoscaling`,`s3`, `ecs`]
- **Region Customization**: Scan specific regions or use default region sets
- **Worker Configuration**: Configurable parallel workers for optimal performance
- **Dry Run Mode**: Preview scan operations without execution
- **Cache Management**: Enable/disable caching as needed
- **Resource Groups API**: Discover 100+ AWS services with `tags`.

### 🛡️ Reliability & Performance
- **Error Handling**: Robust error handling with detailed logging
- **Progress Tracking**: Real-time progress indicators for long-running scans
- **Memory Optimization**: Efficient memory usage for large-scale scans
- **Graceful Degradation**: Continues operation even if some services fail

## 🏗️ Supported AWS Services

| Service          | Description                                                                                                             | Resources Scanned                                                 |
|------------------|-------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| **All Services** | With [Resource Groups Tagging API](https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/overview.html) | 100+ AWS services when using tags                                 |
| **EC2**          | Elastic Compute Cloud                                                                                                   | Instances, Security Groups, Key Pairs, Volumes                    |
| **S3**           | Simple Storage Service                                                                                                  | Buckets and their configurations                                  |
| **ECS**          | Elastic Container Service                                                                                               | Clusters, Services, Task Definitions, Capacity Providers          |
| **VPC**          | Virtual Private Cloud                                                                                                   | VPCs, Subnets, Route Tables, Internet Gateways, NAT Gateways      |
| **Auto Scaling** | Auto Scaling Groups                                                                                                     | ASGs, Launch Configurations, Launch Templates                     |
| **ELB**          | Elastic Load Balancing                                                                                                  | Application Load Balancers, Network Load Balancers, Target Groups |

> **📚 Architecture Details**: For detailed information about the scanning architecture and service implementation patterns, see [Architecture Documentation](docs/aws-scanner-book.md).

## 📋 Prerequisites

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

> [!Tip]
> For detailed setup instructions and troubleshooting, see [setup.sh](setup.sh).

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

## 💻 Usage

### Command Structure

All commands follow this pattern:
```bash
poetry run aws-scanner [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS]
```

**Global Options** (apply to all commands):
- `--verbose` / `-v`: Enable AWS API tracing (use with --debug)
- `--log-file` / `-l`: Custom log file path

**Commands**:
- `scan`: Main scanning command with various options

### Basic Commands

```bash
# Display help and available commands
poetry run aws-scanner --help

# Display scan command help and options
poetry run aws-scanner scan --help

# Basic scan with default settings (all supported services)
poetry run aws-scanner scan --regions us-east-1,eu-west-1,eu-central-1,us-west-2

# Scan specific services
poetry run aws-scanner scan --service ec2

# Scan specific regions
poetry run aws-scanner scan --regions us-east-1,eu-west-1
```

### Debug and Logging Options

```bash
# Enable debug mode for detailed execution traces
poetry run aws-scanner scan --debug --regions us-east-1

# Enable verbose AWS API tracing (requires --debug)
poetry run aws-scanner --verbose scan --debug --service ec2

# Custom log file for debug output
poetry run aws-scanner --log-file /tmp/my-scan.log scan --debug --regions us-east-1

# Combine verbose logging with custom log file
poetry run aws-scanner --verbose --log-file /tmp/aws-api-trace.log scan --debug --service ec2,s3

# Debug with dry run (no actual scanning)
poetry run aws-scanner --verbose scan --debug --dry-run --service vpc
```

### Service-Specific Scanning

```bash
# Scan only EC2 resources
poetry run aws-scanner scan --service ec2

# Scan multiple services
poetry run aws-scanner scan --service ec2 --service s3 --service vpc

# Scan all built-in services in specific regions
poetry run aws-scanner scan --regions us-east-1,us-west-2

# Combine service and region filtering
poetry run aws-scanner scan --service ec2 --regions eu-central-1,eu-west-1

# Scan ALL AWS services using Resource Groups API (requires tags)
poetry run aws-scanner scan --all-services --tag-key Environment --tag-value Production
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

# Continuous refresh mode with custom interval
poetry run aws-scanner scan --refresh --refresh-interval 30 --service ec2

# Debug mode with performance timing
poetry run aws-scanner --verbose scan --debug --max-workers 1 --service ec2
```

### Real-World Examples

```bash
# Production infrastructure audit with comprehensive logging
poetry run aws-scanner --verbose --log-file prod-audit.log scan \
    --debug --tag-key Environment --tag-value Production \
    --format json --output production-audit.json

# Regional compliance check with detailed tracing
poetry run aws-scanner --verbose --log-file compliance-trace.log scan \
    --debug --regions eu-west-1,eu-central-1 \
    --service ec2 --format md --output eu-compliance-report.md

# Application-specific resource discovery across all AWS services
poetry run aws-scanner scan \
    --all-services --tag-key Application --tag-value MyApp \
    --format table --regions us-east-1

# Development environment troubleshooting with verbose logging
poetry run aws-scanner --verbose --log-file dev-debug.log scan \
    --debug --regions us-west-2 \
    --tag-key Environment --tag-value Development \
    --no-cache --dry-run

# Performance analysis with sequential processing
poetry run aws-scanner --verbose --log-file perf-analysis.log scan \
    --debug --max-workers 1 --service-workers 1 \
    --service ec2 --service s3 --regions us-east-1
```

## 🔧 Configuration

### AWS Profile Configuration

```bash
# Set AWS profile
export AWS_PROFILE=your-profile-name

# Login via SSO
aws sso login --profile $AWS_PROFILE

# Verify credentials
aws sts get-caller-identity
```

### Logging Configuration

The scanner features a comprehensive logging system with multiple configuration options:

```bash
# Global logging options (apply to all commands)
poetry run aws-scanner --verbose --log-file /path/to/logfile.log scan --debug

# Debug modes explained:
# --debug: Enable debug mode with rich console output and file logging
# --verbose: Enable AWS API tracing (requires --debug)
# --log-file: Custom log file path (default: .debug_logs/aws_scanner_debug_TIMESTAMP.log)
```

**Logging Levels:**
- **Normal**: Basic progress and results
- **Debug** (`--debug`): Detailed execution traces, timing information, caller context
- **Verbose** (`--verbose` + `--debug`): Full AWS API tracing including HTTP requests/responses

> [!Tip]
> **📖 Detailed Logging Guide**: For comprehensive logging documentation, configuration examples, and troubleshooting, see [Logging Architecture](docs/LOGGING_ARCHITECTURE.md).

### Performance Tuning

- **Max Workers**: Adjust `--max-workers` (1-20) for region-level parallelism
- **Service Workers**: Adjust `--service-workers` (1-10) for service-level parallelism
- **Caching**: Use `--cache` for faster subsequent scans, `--no-cache` for fresh data
- **Debug Impact**: Verbose logging adds ~10-20% overhead; use selectively

## 📁 **Project Structure**

```
aws-resource-scanner/
├── aws_scanner.py               # Core AWS scanning orchestrator
├── cli.py                       # Command-line interface with global options
├── setup.sh                     # Automated setup script
├── run_quick_tests.sh           # Test verification script
├── pyproject.toml               # Project configuration and dependencies
│
├── services/                    # Service-specific scanners
│   ├── ec2_service.py           # EC2 instances, security groups, volumes
│   ├── s3_service.py            # S3 buckets and configurations
│   ├── ecs_service.py           # ECS clusters, services, task definitions
│   ├── vpc_service.py           # VPC networking components
│   ├── autoscaling_service.py   # Auto Scaling groups and configurations
│   └── elb_service.py           # Load balancers and target groups
│
├── aws_scanner_lib/             # Core library modules
│   ├── logging.py               # Unified logging system with AWS API tracing
│   ├── cache.py                 # Intelligent caching with TTL
│   ├── outputs.py               # Multi-format output processing
│   ├── resource_groups_utils.py # Resource Groups API for --all-services
│   └── scan.py                  # Core scanning orchestration logic
│
├── docs/                        # Comprehensive documentation
│   ├── LOGGING_ARCHITECTURE.md  # Detailed logging system documentation
│   └── Architecture.md          # System architecture and design patterns
│
└── tests/                       # Test suite and verification scripts
```

## 🧪 Testing

```bash
# Run all tests
./run_quick_tests.sh

# Run specific test files
poetry run python -m pytest tests/test_aws_scanner.py

# Run with coverage
poetry run python -m pytest --cov=aws_scanner_lib tests/
```

## 🐛 Troubleshooting

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

### Debug and Logging Troubleshooting

The advanced logging system provides powerful debugging capabilities:

```bash
# Basic debug information
poetry run aws-scanner scan --debug --dry-run

# Verbose AWS API tracing for troubleshooting
poetry run aws-scanner --verbose --log-file debug-trace.log scan --debug --service ec2

# Check debug log files (automatically created)
ls .debug_logs/

# Monitor real-time logging
tail -f .debug_logs/aws_scanner_debug_*.log

# Filter AWS API calls
grep -E "(boto|botocore|HTTP)" .debug_logs/aws_scanner_debug_*.log
```

**Logging Troubleshooting Guide:**
- **No AWS API logs visible**: Ensure both `--debug` and `--verbose` flags are used
- **Performance issues**: Verbose logging adds overhead; use `--max-workers 1` for sequential debugging
- **Missing log files**: Check permissions in `.debug_logs/` directory

> [!Tip]
> **🔧 Advanced Troubleshooting**: For detailed logging troubleshooting and configuration options, see [Logging Architecture - Troubleshooting Section](docs/LOGGING_ARCHITECTURE.md#troubleshooting).

## � Quick Reference

### Most Common Commands

```bash
# Quick scan with basic output
poetry run aws-scanner scan --regions us-east-1

# Debug mode with detailed logging
poetry run aws-scanner scan --debug --regions us-east-1

# Full AWS API tracing (development/troubleshooting)
poetry run aws-scanner --verbose --log-file trace.log scan --debug --service ec2

# Tag-based filtering across all AWS services
poetry run aws-scanner scan --all-services --tag-key Environment --tag-value Production

# Production audit with comprehensive logging
poetry run aws-scanner --verbose --log-file audit.log scan --debug \
    --tag-key Environment --tag-value Production --format json --output audit.json
```

### Flag Combinations Guide

| Scenario         | Command Pattern                                          | Purpose                        |
|------------------|----------------------------------------------------------|--------------------------------|
| **Basic Scan**   | `poetry run aws-scanner scan`                            | Standard resource discovery    |
| **Debug Mode**   | `poetry run aws-scanner scan --debug`                    | Detailed execution information |
| **API Tracing**  | `poetry run aws-scanner --verbose scan --debug`          | Full AWS API call logging      |
| **Custom Logs**  | `poetry run aws-scanner --log-file path scan --debug`    | Custom log file location       |
| **All Services** | `poetry run aws-scanner scan --all-services --tag-key X` | Discover 100+ AWS services     |

## 📖 Documentation

The project includes comprehensive documentation covering all aspects of the system:

- **[Architecture Documentation](docs/Architecture.md)**: System design, component interactions, and architectural patterns
- **[Logging Architecture](docs/LOGGING_ARCHITECTURE.md)**: Complete logging system guide including:
  - AWS API tracing capabilities
  - Configuration examples
  - External integration patterns
  - Troubleshooting guide
  - Performance considerations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install development dependencies: Use [`./setup.sh`](./setup.sh)
4. Set up pre-commit hooks: `pre-commit install --install-hooks`
5. Make your changes and run tests: `./run_quick_tests.sh`
6. Test logging changes: `poetry run aws-scanner --verbose scan --debug --dry-run`
7. Commit your changes: `git commit -m 'Add amazing feature'`
8. Push to the branch: `git push origin feature/amazing-feature`
9. Open a Pull Request

> [!TIP]
> **Development Notes:**
> - Use the debug and verbose flags extensively during development
> - Check the logging architecture documentation when modifying logging behavior
> - Ensure all new features include appropriate logging and error handling

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/) for CLI interface
- Styled with [Rich](https://rich.readthedocs.io/) for beautiful console output
- Powered by [Boto3](https://boto3.amazonaws.com/) for AWS integration
- Managed with [Poetry](https://python-poetry.org/) for dependency management

---

> _Made with ❤️ for the AWS community_
