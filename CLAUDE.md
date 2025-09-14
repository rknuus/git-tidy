# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Git-tidy is a Python package that provides tools for intelligently reordering git commits by grouping them based on file similarity. The project is structured as a proper Python package with uv support and can be published to PyPI.

## Commands

### Development Setup
```bash
# Install with development dependencies
uv sync --dev

# Install package in development mode
uv pip install -e .
```

### Running the CLI
```bash
# After installation, use the git-tidy command with subcommands
git-tidy group-commits [options]

# Or run directly from source
uv run python -m git_tidy.cli group-commits [options]

# Show help for all commands
git-tidy --help

# Show help for specific command
git-tidy group-commits --help
```

### Development Commands

**Using Makefile (recommended):**
```bash
# Show all available commands
make help

# Set up development environment
make dev-setup

# Run all quality checks
make quality-checks

# Fix code quality issues
make quality-fix

# Run tests
make test

# Run full CI pipeline
make ci-checks

# Clean build artifacts
make clean
```

**Manual commands:**
```bash
# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy src/

# Format code
uv run black .
```

### Available Commands

#### `group-commits`
Groups commits by file similarity and reorders them.

**Options:**
- `--base BASE`: Specify base commit/branch for rebase range (defaults to merge-base with main/master)
- `--threshold THRESHOLD`: Set similarity threshold (0.0-1.0, default: 0.3)
- `--dry-run`: Show proposed grouping without performing the actual rebase

### Examples
```bash
# Analyze and group commits with default settings
git-tidy group-commits

# Preview grouping without making changes
git-tidy group-commits --dry-run

# Use custom similarity threshold
git-tidy group-commits --threshold 0.5

# Specify custom base for rebase range
git-tidy group-commits --base origin/main
```

## Architecture

### Core Components

**GitTidy Class** (`src/git_tidy/core.py:16-243`):
- Main orchestrator that handles the entire workflow
- Manages git operations, backup/restore functionality, and user interaction

**Key Methods**:
- `get_commits_to_rebase()`: Identifies commit range from base to HEAD, defaults to merge-base with main/master
- `group_commits()`: Uses greedy algorithm with Jaccard similarity to group commits by file overlap
- `calculate_similarity()`: Computes file similarity using Jaccard index (intersection/union)
- `perform_rebase()`: Executes interactive rebase using generated todo list

### Algorithm Details

The commit grouping uses a **greedy clustering approach**:
1. Iterates through commits in chronological order
2. For each ungrouped commit, starts a new group
3. Scans remaining commits for similarity above threshold
4. Groups commits that share significant file overlap

**Similarity Calculation**: Uses Jaccard similarity coefficient between file sets:
```
similarity = |files1 ∩ files2| / |files1 ∪ files2|
```

### Safety Features

- **Automatic backup**: Creates backup branch before any operations
- **Error recovery**: Restores original state on failure
- **User confirmation**: Prompts before executing rebase
- **Dry-run mode**: Preview changes without modification

### Package Structure

```
src/git_tidy/
├── __init__.py          # Package exports
├── core.py              # Main GitTidy class and logic
└── cli.py               # Command-line interface

tests/
├── __init__.py
└── test_core.py         # Unit tests for core functionality
```

### Dependencies

- Python 3.8+ (uses type hints, f-strings)
- Standard library only: subprocess, sys, json, typing, collections, tempfile, os
- Git (executed via subprocess calls)
- Development dependencies: pytest, black, ruff, mypy

## Development Notes

- Proper Python package structure with src/ layout
- Uses uv for dependency management and packaging
- CLI entry point defined in pyproject.toml
- Uses subprocess to interact with git commands
- Implements custom GitError exception for git operation failures
- Interactive rebase performed via temporary todo file and GIT_SEQUENCE_EDITOR
- Includes basic unit tests for core functionality