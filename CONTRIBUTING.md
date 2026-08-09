# Contributing to Home Assistant Test Harness

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

See the [Development Guide](docs/development.md) for complete setup instructions.

Quick start:

```bash
git clone https://github.com/HeadlessTarry/HomeAssistant-Test-Harness.git
cd HomeAssistant-Test-Harness
./setup_dev_env.sh
```

This script will:

- Install all development dependencies using `uv`
- Set up pre-commit hooks
- Creates a `.env` file for local environment variables
- Runs initial validation

## Code Standards

This project maintains high code quality standards:

- **Style Guide**: See [Development Guide - Code Standards](docs/development.md#code-standards)
- **Pre-commit Hooks**: Automatically enforced via `.pre-commit-config.yaml`
  - black (formatting)
  - isort (import sorting)
  - flake8 (linting)
  - mypy (type checking)
  - yamllint (YAML linting)
  - markdownlint (Markdown linting)
  - shellcheck (shell script linting)
- **Type Hints**: Required for all public APIs (mypy strict mode)
- **Line Length**: 200 characters
- **Docstrings**: Google style for classes and methods

## Making Changes

1. **Fork the repository** and create a feature branch from `main`
2. **Make your changes** following the code standards
3. **Run validation** to ensure all checks pass:

   ```bash
   ./run_checks.sh
   ```

4. **Commit your changes** with clear, descriptive commit messages. **Never use `git commit --no-verify`** - if pre-commit hooks fail, fix the underlying issues instead of bypassing the checks.
5. **Push to your fork** and submit a pull request

## Pull Request Guidelines

- **Clear description**: Explain what changes you made and why
- **Link related issues**: Use `Fixes #123` or `Relates to #456` in the description
- **Keep PRs focused**: One feature or fix per PR
- **All checks must pass**: Pre-commit hooks, build validation, and example tests
- **Be responsive**: Address review feedback in a timely manner

## Testing

This project uses a pragmatic testing approach:

- **Validation Script**: Run `./run_checks.sh` to execute all quality checks, build the package, and run example tests
- **Example Tests**: Located in `examples/` directory - these serve as both documentation and validation
- **Manual Testing**: Test your changes in a real Home Assistant configuration repository

See the [Development Guide - Testing](docs/development.md#testing-the-package) for more details.

## Reporting Issues

When reporting issues, please include:

- **Clear description** of the problem
- **Steps to reproduce** the issue
- **Expected vs actual behavior**
- **Environment details**: Python version, Docker version, OS
- **Relevant logs** or error messages

## Code Review Process

All contributions go through code review:

1. **Automated checks** must pass (CI/CD workflows)
2. **Code review** by maintainers
3. **Changes requested** if needed
4. **Approval and merge** once all requirements are met

Repository rulesets enforce PR reviews and required checks before merging.

## Development Tips

- **Run checks early and often**: Use `./run_checks.sh` frequently to catch issues early
- **Test in real repos**: Install your changes in editable mode (`uv pip install -e /path/to/harness`) and test with real Home Assistant configurations
- **Ask questions**: Open an issue for discussion if you're unsure about an approach
- **Start small**: Consider starting with documentation improvements or small bug fixes to get familiar with the codebase

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code. Please report unacceptable behavior to the contributors.

## Questions

- **Documentation**: Check the [documentation](docs/) directory
- **Issues**: Search [existing issues](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues)
- **New questions**: Open a new issue with the question label

## License

By contributing to this project, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

Thank you for contributing! 🎉
