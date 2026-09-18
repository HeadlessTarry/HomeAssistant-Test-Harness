# CLAUDE.md

This file provides guidance to AI agents when working with code in this repository.

## 🏠 Overview

A pytest plugin (`ha_integration_test_harness`) for integration testing Home Assistant and AppDaemon
configurations using real Docker containers — no mocks.

## 🚪 Gate

**Before making changes:** Create a worktree, then run `./setup_dev_env.sh`.
See **[docs/development.md](docs/development.md)** — When setting up the development environment:
worktrees, prerequisites, VS Code, interactive environment.

**Before committing:** Run `./run_checks.sh` and fix all failures.
See **[docs/development.md](docs/development.md#running-checks)** — When running checks:
pre-commit hooks, unit tests, integration tests, and what each check validates.

These are not optional. Skipping them will cause CI failures.

## 📚 Documentation

- **[CONTEXT.md](CONTEXT.md)** — When understanding domain terminology: virtual entities, persistent entities, test rollback, downstream projects
- **[docs/installation.md](docs/installation.md)** — When installing the harness: pip, poetry, verification, requirements
- **[docs/usage.md](docs/usage.md)** — When getting started: auto-discovery, container lifecycle, configuration requirements
- **[docs/architecture.md](docs/architecture.md)** — When understanding the test environment: container layout, startup sequence, parallel execution, HA image override
- **[docs/writing-tests.md](docs/writing-tests.md)** — When writing tests: basic patterns, time-based tests, calling actions, polling
- **[docs/persistent-entities.md](docs/persistent-entities.md)** — When you need entities available across multiple tests: YAML configuration, startup behavior, comparison with per-test entities
- **[docs/best-practices.md](docs/best-practices.md)** — When optimizing test patterns: cleanup strategies, factory fixtures, area/label testing
- **[docs/fixtures.md](docs/fixtures.md)** — When understanding available fixtures: docker, home_assistant, app_daemon, time_machine
- **[docs/home-assistant-fixture.md](docs/home-assistant-fixture.md)** — When interacting with Home Assistant: entity management, state assertions, action calls, area/label assignment
- **[docs/app-daemon-fixture.md](docs/app-daemon-fixture.md)** — When working with AppDaemon: basic API access
- **[docs/time-machine-fixture.md](docs/time-machine-fixture.md)** — When testing time-based automations: forward-only constraint, DST handling, session-scoped persistence, sunrise/sunset presets
- **[docs/troubleshooting.md](docs/troubleshooting.md)** — When encountering issues: common errors, debugging tips
- **[docs/development.md](docs/development.md)** — When contributing to the harness: development environment, running checks, code style, releases
- **[docs/adr/](docs/adr/)** — When understanding why a design decision was made: architecture decision records

## 🤖 Agent skills

- **[docs/agents/issue-tracker.md](docs/agents/issue-tracker.md)** — When filing or triaging issues: GitHub Issues workflow
- **[docs/agents/triage-labels.md](docs/agents/triage-labels.md)** — When applying triage labels: canonical label vocabulary
- **[docs/agents/domain.md](docs/agents/domain.md)** — When navigating domain docs: CONTEXT.md layout, ADR conventions
