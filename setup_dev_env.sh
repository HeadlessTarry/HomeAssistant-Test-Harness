#!/bin/bash
set -e
set -o pipefail

echo "🛠️ Installing development dependencies..."
if [[ -n "$GITHUB_ACTIONS" ]]; then
    uv sync --all-extras --frozen
else
    uv sync --all-extras
fi

echo ""
echo "🪝 Setting up git hooks..."
uv run pre-commit install

echo ""
echo "🌱 Creating .env file..."
if [ -f .env ]; then
    echo "⚠️  .env file already exists. Backing up to .env.backup"
    cp .env .env.backup
fi
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # On Windows (Git Bash/MSYS2), convert to Windows format
    ROOT_PATH=$(cygpath -m "$(pwd)")
else
    # On Linux/macOS, use the standard absolute path
    ROOT_PATH="$(pwd)"
fi
echo "HOME_ASSISTANT_CONFIG_ROOT=\"$ROOT_PATH/examples/home_assistant\"" > .env

echo ""
echo "🔍 Let's just check everything is working..."
if [[ "$1" != "--skip-checks" ]]; then
  ./run_checks.sh
fi
