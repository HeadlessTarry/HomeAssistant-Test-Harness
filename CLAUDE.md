# CLAUDE.md

This file provides guidance to AI agents when working with code in this repository.

## ⚠️ Mandatory First Steps

**Before making ANY changes to this codebase:**

1. Create a git worktree (see "Worktree Setup" below)
2. Run `./setup_dev_env.sh` in the worktree
3. Only then start making changes

**Before committing ANY changes:**

1. Run `./run_checks.sh` and fix ALL failures
2. Repeat until all checks pass
3. Only then commit

These are not optional. Skipping them will cause CI failures.

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

## Worktree Setup

### Sequence: create worktree → run setup → make changes

```bash
git worktree add .worktrees/feature-name -b feature/feature-name
cd .worktrees/feature-name
./setup_dev_env.sh
```

Worktrees have isolated virtual environments. The setup script installs dependencies
(including `pre-commit`) into the worktree's venv and configures git hooks. Skipping
this step will cause pre-commit hooks to fail or be unavailable.

## Commit Workflow

**Before committing, always run `./run_checks.sh` and fix all failures.**

Never bypass validation with individual commands like `uv run pre-commit run`
or `git commit --no-verify`. The `./run_checks.sh` script performs comprehensive
validation (pre-commit hooks, build, install test, example tests) that individual
commands cannot replicate.

If `./run_checks.sh` fails:

1. Fix the underlying issues (formatting, linting, type errors, test failures)
2. Re-run `./run_checks.sh` until all checks pass
3. Only then commit and push

Pre-commit hooks enforce code quality standards (black, isort, flake8, mypy, yamllint, markdownlint). These must pass before code is merged.

## Common Mistakes to Avoid

❌ **Don't** run `pytest` directly without first running `./setup_dev_env.sh`
❌ **Don't** commit without running `./run_checks.sh` first
❌ **Don't** use `uv run pre-commit run` instead of `./run_checks.sh`
❌ **Don't** skip worktree setup - each worktree needs its own environment
❌ **Don't** make changes on the main branch - always use a worktree

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
