# Poetry Installation and Migration Guide

## Step 1: Install Poetry

### Option A: Using the official installer (Recommended)
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### Option B: Using pip (if you prefer)
```bash
pip install poetry
```

### Option C: Using Homebrew (macOS)
```bash
brew install poetry
```

## Step 2: Verify Poetry Installation
```bash
poetry --version
```
Expected output: `Poetry (version 1.x.x)`

## Step 3: Add Poetry to PATH (if needed)
Add this to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Then reload your shell:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

## Step 4: Configure Poetry (Optional but recommended)
```bash
# Set virtual environments to be created in project directory
poetry config virtualenvs.in-project true

# Verify configuration
poetry config --list
```

## Step 5: Remove Current Virtual Environment
```bash
# Deactivate current environment if active
deactivate

# Remove the .venv directory
rm -rf .venv

# Remove __pycache__ directories
find . -name "__pycache__" -type d -exec rm -rf {} +

# Remove .egg-info directory
rm -rf aws_service_scanner.egg-info
```

## Step 6: Initialize Poetry Project
```bash
# This will use the existing pyproject.toml
poetry install
```

## Step 7: Verify New Environment
```bash
# Activate the new Poetry environment
poetry shell

# Check Python version and packages
poetry run python --version
poetry show

# Test your application
poetry run python aws_scanner.py --help
```

## Step 8: Remove Old Files (Optional)
After confirming everything works:
```bash
# Remove old dependency files
rm requirements.txt
rm requirements-docker.txt
rm setup.py
rm MANIFEST.in

# Remove old build artifacts
rm -rf build/
rm -rf dist/
```

## Step 9: Update Scripts and Documentation
Update any scripts or documentation that reference:
- `pip install -r requirements.txt` → `poetry install`
- `python setup.py install` → `poetry install`
- `pip install .` → `poetry install`

## What Changes After Migration:

### Dependencies:
- **Before**: `pip install -r requirements.txt`
- **After**: `poetry install`

### Adding new packages:
- **Before**: `pip install package_name` → manually add to requirements.txt
- **After**: `poetry add package_name` (automatically updates pyproject.toml and poetry.lock)

### Virtual Environment:
- **Before**: Manual venv creation with `python -m venv .venv`
- **After**: `poetry install` creates and manages venv automatically

### Running scripts:
- **Before**: `python aws_scanner.py`
- **After**: `poetry run python aws_scanner.py` or activate with `poetry shell`

### Lock file:
- **Before**: requirements.txt with exact versions
- **After**: poetry.lock file with exact versions + dependency tree

### Development dependencies:
- **Before**: Separate requirements-dev.txt file
- **After**: `[tool.poetry.group.dev.dependencies]` section in pyproject.toml

## Benefits of Poetry:

1. **Dependency Resolution**: Poetry resolves conflicts automatically
2. **Lock File**: poetry.lock ensures reproducible builds
3. **Virtual Environment Management**: Automatic venv creation and management
4. **Publishing**: Easy package publishing to PyPI
5. **Scripts**: Define CLI entry points in pyproject.toml
6. **Development Dependencies**: Separate dev dependencies
7. **Modern Standards**: Uses pyproject.toml (PEP 518)

## Common Poetry Commands:

```bash
# Install dependencies
poetry install

# Add a new dependency
poetry add boto3

# Add a development dependency
poetry add pytest --group dev

# Remove a dependency
poetry remove package_name

# Update dependencies
poetry update

# Show dependency tree
poetry show --tree

# Activate virtual environment
 poetry env activate

# Run command in environment
poetry run python script.py

# Build package
poetry build

# Publish to PyPI
poetry publish
```

## Troubleshooting:

### If Poetry installation fails:
```bash
# Try with --break-system-packages if on system Python
pip install poetry --break-system-packages

# Or use pipx (recommended)
pip install pipx
pipx install poetry
```

### If virtual environment issues:
```bash
# Remove Poetry cache
poetry cache clear pypi --all

# Remove and recreate venv
poetry env remove python
poetry install
```

### If dependency conflicts:
```bash
# Check for conflicts
poetry check

# Try resolving with --no-dev for production only
poetry install --no-dev
```
