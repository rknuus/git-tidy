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

After installation, you can use the `git-tidy` command with the most useful subcommands:

```bash
# Show available commands
git-tidy --help

# Orchestrated, safe rebase with dedup and validation (recommended)
git-tidy smart-rebase --base origin/main --prompt --optimize-merge

# Rebase onto base while skipping content already merged (patch-id aware)
git-tidy rebase-skip-merged --base origin/main --no-prompt --optimize-merge

# Configure repository with safer merge/rebase defaults (idempotent)
git-tidy configure-repo --scope local --preset safe

# Group commits by file similarity (optional preparation step)
git-tidy group-commits

# Preview grouping without making changes
git-tidy group-commits --dry-run

# Use custom similarity threshold
git-tidy group-commits --threshold 0.5

# Specify custom base for rebase range
git-tidy group-commits --base origin/main

# Split commits into per-file commits (optional surgery)
git-tidy split-commits --dry-run
```

### Core Commands

#### `smart-rebase`
Performs an orchestrated rebase with preflight checks, base selection, dedup-aware replay, optional chunking/trivial auto-resolve, and post-run validation/reporting.

Key options:
- `--branch BRANCH`, `--base BASE`
- `--[no-]prompt` (default: on), `--[no-]backup` (default: on)
- `--[no-]optimize-merge` (temporary safe merge settings)
- `--conflict-bias=ours|theirs|none` (default: none)
- `--chunk-size N`, `--[no-]auto-resolve-trivial`, `--max-conflicts N`
- `--[no-]rename-detect`, `--[no-]lint`, `--[no-]test`, `--[no-]build`

#### `rebase-skip-merged`
Rebases the current (or given) branch onto a base while skipping commits whose content is already on the base (via patch-id equivalence). Great when an ancestor branch was rebased but landed unchanged on main.

Key options:
- `--base BASE`, `--branch BRANCH`, `--[no-]dry-run`
- `--[no-]prompt`, `--[no-]backup`
- `--[no-]optimize-merge`, `--conflict-bias=ours|theirs|none`
- `--chunk-size N`, `--max-conflicts N`, `--[no-]auto-resolve-trivial`

#### `configure-repo`
Applies safe, idempotent git configuration to reduce merge/rebase pain.

Key options:
- `--scope local|global` (default: local)
- `--preset safe|opinionated|custom` (currently safe preset implemented)

#### `group-commits`
Groups commits by file similarity and reorders them while preserving relative order within each group.

Key options:
- `--base BASE` (defaults to merge-base with main/master)
- `--threshold FLOAT` (default: 0.3)
- `--[no-]dry-run`

#### `split-commits`
Splits each commit in the range into separate commits, one per file.

Key options:
- `--base BASE`, `--[no-]dry-run`

### Advanced/Utility
- `select-base`, `preflight-check`, `auto-continue`, `auto-resolve-trivial`, `range-diff-report`, `rerere-share`, `checkpoint-create`, `checkpoint-restore` — helper commands used by `smart-rebase` and available for advanced workflows.

## How it works

Git-tidy analyzes your commit history and groups commits that touch similar files together while preserving the relative order within each group. It uses a greedy clustering approach with Jaccard similarity to determine file overlap.

### Safety Features

- **Automatic backup**: Creates backup branch before any operations
- **Error recovery**: Restores original state on failure
- **User confirmation**: Prompts before executing rebase
- **Dry-run mode**: Preview changes without modification

### Examples
```bash
# Smart rebase with safe settings and prompts
git-tidy smart-rebase --base origin/main --prompt --optimize-merge

# Skip-merged rebase without prompts; bias to 'theirs' on conflicts
git-tidy rebase-skip-merged --base origin/main --no-prompt --conflict-bias=theirs

# Configure current repo with safe settings
git-tidy configure-repo --scope local
```

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