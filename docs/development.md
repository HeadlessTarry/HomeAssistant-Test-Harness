# Development Guide

## Setting Up Development Environment

### Prerequisites

- Python 3.14.2+
- Docker Engine
- Docker Compose V2
- Git

### Clone and Install

```bash
git clone https://github.com/HeadlessTarry/HomeAssistant-Test-Harness.git
cd HomeAssistant-Test-Harness
./setup_dev_env.sh
```

This script:

1. Installs all development dependencies using `uv`
2. Sets up pre-commit hooks
3. Creates a `.env` file for local environment variables
4. Runs initial validation (pre-commit checks, build, tests)

**Skip initial validation:** If you want to skip the initial checks, use:

```bash
./setup_dev_env.sh --skip-checks
```

## Running Checks

### Run All Checks

The `run_checks.sh` script runs all validation steps:

```bash
./run_checks.sh
```

This script:

1. Runs all pre-commit hooks (black, isort, flake8, mypy, yamllint, markdownlint)
2. Builds the package distribution
3. Tests package installation and imports
4. Runs example tests

### Individual Tools

You can also run individual checks:

```bash
# Format code
black src/

# Sort imports
isort src/

# Lint
flake8 src/

# Type check
mypy src/

# Lint YAML
yamllint .

# Lint Markdown
markdownlint_docker --style .markdownlint_style.rb .
```

## Testing the Package

### Complete Validation

Run the complete validation suite (includes building, testing installation, and running examples):

```bash
./run_checks.sh
```

## Using Editable Install in Another Project

When developing the harness, you can use it as a dev dependency in your Home Assistant configuration repository.

Add to your `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "ha-integration-test-harness @ file:///path/to/HomeAssistant-Test-Harness",
]
```

Or install directly:

```bash
# In your HomeAssistant configuration repository
pip install -e /path/to/HomeAssistant-Test-Harness

# Run your integration tests
pytest integration_tests/
```

This allows you to:

- Make changes to the harness code
- Test changes immediately without reinstalling
- Develop features while testing against real configuration

## Semantic Versioning

Follow [semantic versioning](https://semver.org/):

- **Major** (1.0.0): Breaking changes to fixtures or API
- **Minor** (0.2.0): New features, backward compatible
- **Patch** (0.1.1): Bug fixes, backward compatible

### Version Bump Examples

- Fixture signature changes: **Major**
- New fixture added: **Minor**
- Docker configuration improvements: **Minor**
- Bug fix in API client: **Patch**
- Documentation updates: **Patch**

## Creating Releases

### Process

**Create release via GitHub Actions**:

- Go to Actions → "Create Release"
- Click "Run workflow"
- Enter the version number (e.g., `0.2.0`)
- Choose whether to publish immediately or create draft
- Workflow will:
  - Update version in pyproject.toml
  - Regenerate uv.lock with the new version
  - Commit and push both files
  - Create a git tag `v<version>` (e.g., `v0.2.0`)
  - Create the GitHub release

### Release Tag Format

Releases use version tags with a `v` prefix (e.g., `v0.2.0`).

### After Release

- GitHub automatically generates release notes
- Users can install specific release as a dev dependency in their `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "ha-integration-test-harness @ git+https://github.com/HeadlessTarry/HomeAssistant-Test-Harness.git@v0.2.0",
]
```

## Code Style

### Python

- **Line length**: 200 characters
- **Formatter**: Black
- **Import sorting**: isort (black profile)
- **Type hints**: Required for all public APIs
- **Docstrings**: Google style

### YAML

- **Indentation**: 2 spaces
- **Line length**: 200 characters
- **No trailing whitespace**

### Markdown

- **Line length**: 200 characters
- **List indentation**: 2 spaces
- **Ordered lists**: sequential numbering

## Project Structure

```tree
HomeAssistant-Test-Harness/
├── src/ha_integration_test_harness/  # Package source
│   ├── __init__.py                    # Public API exports
│   ├── conftest.py                    # Pytest plugin fixtures
│   ├── docker_manager.py              # Docker orchestration
│   ├── homeassistant_client.py        # HA API client
│   ├── appdaemon_client.py            # AppDaemon client
│   ├── time_machine.py                # Time manipulation
│   ├── exceptions.py                  # Exception hierarchy
│   └── containers/                    # Docker configurations
│       ├── docker-compose.yaml
│       ├── homeassistant/             # HA setup scripts
│       ├── appdaemon/                 # AppDaemon setup
│       └── libfaketime/               # Time manipulation
├── examples/                          # Example tests
│   ├── test_basic_usage.py
│   └── config/                        # Minimal HA config
├── docs/                              # User documentation
├── .github/workflows/                 # CI/CD pipelines
├── pyproject.toml                     # Package metadata
└── README.md                          # Project overview
```

## CI/CD

### Continuous Integration

The CI workflow runs on every push and pull request:

1. Installs dependencies
2. Runs pre-commit hooks
3. Builds package
4. Validates package imports

### Release Workflow

Manual trigger creates timestamped release with auto-generated notes.

## Next Steps

- Check [GitHub Issues](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues) for tasks
- Join discussions in issue tracker
