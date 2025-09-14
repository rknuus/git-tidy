# git-tidy

A tool for intelligently reordering git commits by grouping them based on file similarity.

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

After installation, you can use the `git-tidy` command:

```bash
# Analyze and group commits with default settings
git-tidy

# Preview grouping without making changes
git-tidy --dry-run

# Use custom similarity threshold
git-tidy --threshold 0.5

# Specify custom base for rebase range
git-tidy --base origin/main
```

### Options

- `--base BASE`: Specify base commit/branch for rebase range (defaults to merge-base with main/master)
- `--threshold THRESHOLD`: Set similarity threshold (0.0-1.0, default: 0.3)
- `--dry-run`: Show proposed grouping without performing the actual rebase

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

MIT