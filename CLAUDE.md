# CLAUDE.md

This file provides guidance to AI agents when working with code in this repository.

## What This Is

A pytest plugin (`ha_integration_test_harness`) for integration testing Home Assistant and AppDaemon
configurations using real Docker containers — no mocks.

## Commands

```bash
# Initial setup (installs deps via uv, sets up pre-commit, creates .env)
./setup_dev_env.sh

# Full validation: pre-commit hooks + build + install test + example tests
./run_checks.sh

# Run example tests
pytest examples/

# Run a single test
pytest examples/test_basic_usage.py::test_entity_state_with_auto_cleanup
```

## Documentation

- [Architecture & key components](docs/development.md)
- [Writing tests](docs/usage.md)
- [Available fixtures](docs/fixtures.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Installation](docs/installation.md)
- [Architecture decisions](docs/adr/)

## Important Constraints

- **Package name**: `ha_integration_test_harness` (underscores)
- **Runtime deps**: Only `requests`, `python-dateutil`, `PyYAML`, `websocket-client`
- **Config mounts are read-write** (not `:ro`)
- **Error messages** for config problems must include the GitHub usage docs link
- **Atomic file writes**: temp-file-then-move

## Agent skills

### Issue tracker

Issues live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.
