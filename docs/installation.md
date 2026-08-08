# Installation Guide

## Requirements

- Python 3.14.2 or later
- Docker Engine (running and accessible)
- Docker Compose V2
- A Home Assistant configuration repository

## Installation

Since this is a **pytest plugin** for testing Home Assistant configurations, it should be installed as a **development dependency** in your Home Assistant configuration repository.

### Method 1: pyproject.toml (Recommended)

Add to your `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "ha-integration-test-harness @ git+https://github.com/HeadlessTarry/HomeAssistant-Test-Harness.git",
    # Add other dev dependencies here (e.g., pytest, black, mypy)
]
```

Then install with:

```bash
pip install -e ".[dev]"
```

### Method 2: requirements-dev.txt

Create a `requirements-dev.txt` file:

```text
ha-integration-test-harness @ git+https://github.com/HeadlessTarry/HomeAssistant-Test-Harness.git
```

Then install with:

```bash
pip install -r requirements-dev.txt
```

### Method 3: Poetry

If you use Poetry:

```bash
poetry add --group dev git+https://github.com/HeadlessTarry/HomeAssistant-Test-Harness.git
```

### Method 4: Direct Install (Not Recommended)

For quick testing only (doesn't add to your project's dependency list):

```bash
pip install git+https://github.com/HeadlessTarry/HomeAssistant-Test-Harness.git
```

## Verification

Verify the installation:

```bash
python -c "import ha_integration_test_harness; print(ha_integration_test_harness.__version__)"
```

## Configuration

No configuration is required. The plugin automatically:

- Registers pytest fixtures when installed
- Detects your repository root
- Mounts your configuration into Docker containers

## Next Steps

- Read the [Usage Guide](usage.md) to learn how to write tests
- Review [Available Fixtures](fixtures.md) to understand what's provided
- Check [Troubleshooting](troubleshooting.md) if you encounter issues
