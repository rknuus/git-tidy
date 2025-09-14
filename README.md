# git-tidy

A tool to automate complicated and tedious git operations, e.g. intelligently reordering git commits by grouping them based on file similarity.

## Installation

### Using uv (recommended)

```bash
uv add git-tidy
```

### Using pip

```bash
pip install git-tidy
```

### Development installation

```bash
git clone <repository-url>
cd git-tidy
uv sync --dev
```

## Usage

After installation, you can use the `git-tidy` command with various subcommands:

```bash
# Show available commands
git-tidy --help

# Group commits by file similarity (main feature)
git-tidy group-commits

# Preview grouping without making changes
git-tidy group-commits --dry-run

# Use custom similarity threshold
git-tidy group-commits --threshold 0.5

# Specify custom base for rebase range
git-tidy group-commits --base origin/main
```

### Commands

#### `group-commits`

Groups commits by file similarity and reorders them while preserving relative order within each group.

**Options:**
- `--base BASE`: Specify base commit/branch for rebase range (defaults to merge-base with main/master)
- `--threshold THRESHOLD`: Set similarity threshold (0.0-1.0, default: 0.3)
- `--dry-run`: Show proposed grouping without performing the actual rebase

**Examples:**
```bash
# Basic usage with default settings
git-tidy group-commits

# Preview changes only
git-tidy group-commits --dry-run

# Custom threshold for more/less grouping
git-tidy group-commits --threshold 0.8  # stricter grouping
git-tidy group-commits --threshold 0.1  # looser grouping

# Specify base commit range
git-tidy group-commits --base HEAD~10
git-tidy group-commits --base origin/main
```

## How it works

Git-tidy analyzes your commit history and groups commits that touch similar files together while preserving the relative order within each group. It uses a greedy clustering approach with Jaccard similarity to determine file overlap.

### Safety Features

- **Automatic backup**: Creates backup branch before any operations
- **Error recovery**: Restores original state on failure
- **User confirmation**: Prompts before executing rebase
- **Dry-run mode**: Preview changes without modification

## Development

This project uses:
- [uv](https://github.com/astral-sh/uv) for dependency management
- [ruff](https://github.com/astral-sh/ruff) for linting
- [black](https://github.com/psf/black) for code formatting
- [mypy](https://github.com/python/mypy) for type checking
- [pytest](https://github.com/pytest-dev/pytest) for testing

### Development commands

The project includes a comprehensive Makefile for common development tasks:

```bash
# Show all available commands
make help

# Set up development environment
make dev-setup

# Run all quality checks (lint, typecheck, format-check)
make quality-checks

# Fix code quality issues automatically
make quality-fix

# Run tests
make test

# Run all CI checks (quality + tests)
make ci-checks

# Clean up build artifacts
make clean
```

#### Manual commands (without Makefile)

```bash
# Install development dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy src/

# Format code
uv run black .
```

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.