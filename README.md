# Home Assistant Integration Test Harness

A pytest plugin for integration testing Home Assistant and AppDaemon configurations using Docker containers.

[![Continuous Integration][ci-badge]][ci-url]
[![Quality Gate Status][quality-badge]][quality-url]
[![License: MIT][license-badge]][license-url]
[![Python 3.14.2+][python-badge]][python-url]
[![Code style: black][black-badge]][black-url]

[ci-badge]: https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/actions/workflows/ci.yaml/badge.svg
[ci-url]: https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/actions/workflows/ci.yaml
[quality-badge]: https://sonarcloud.io/api/project_badges/measure?project=HeadlessTarry_HomeAssistant-Test-Harness&metric=alert_status
[quality-url]: https://sonarcloud.io/summary/new_code?id=HeadlessTarry_HomeAssistant-Test-Harness
[license-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[license-url]: https://opensource.org/licenses/MIT
[python-badge]: https://img.shields.io/badge/python-3.14.2+-blue.svg
[python-url]: https://www.python.org/downloads/
[black-badge]: https://img.shields.io/badge/code%20style-black-000000.svg
[black-url]: https://github.com/psf/black

## ℹ️ About

A pytest plugin (`ha_integration_test_harness`) for integration testing Home Assistant and AppDaemon
configurations using real Docker containers — no mocks. Tests run against real instances, ensuring
your configuration works correctly in an environment that mirrors production.

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

## 🔗 Links

- **Repository**: <https://github.com/HeadlessTarry/HomeAssistant-Test-Harness>
- **Issues**: <https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues>
- **Changelog**: <https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/releases>

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up the development environment
- Code standards and style guide
- Running tests and validation
- Submitting pull requests

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## 🔒 Security

For security issues, please see our [Security Policy](SECURITY.md) for responsible disclosure guidelines.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
