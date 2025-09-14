# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Git-tidy is a Python script that intelligently reorders git commits by grouping them based on file similarity. The tool analyzes commit history and groups commits that touch similar files together while preserving the relative order within each group.

## Commands

### Running the script
```bash
python3 git-tidy.py [options]
```

### Available options
- `--base BASE`: Specify base commit/branch for rebase range (defaults to merge-base with main/master)
- `--threshold THRESHOLD`: Set similarity threshold (0.0-1.0, default: 0.3)
- `--dry-run`: Show proposed grouping without performing the actual rebase

### Examples
```bash
# Analyze and group commits with default settings
python3 git-tidy.py

# Preview grouping without making changes
python3 git-tidy.py --dry-run

# Use custom similarity threshold
python3 git-tidy.py --threshold 0.5

# Specify custom base for rebase range
python3 git-tidy.py --base origin/main
```

## Architecture

### Core Components

**GitTidy Class** (`git-tidy.py:16-243`):
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

### Dependencies

- Python 3.x (uses type hints, f-strings)
- Standard library only: subprocess, sys, json, typing, collections, tempfile, os
- Git (executed via subprocess calls)

## Development Notes

- Single-file Python script with no external dependencies
- Uses subprocess to interact with git commands
- Implements custom GitError exception for git operation failures
- Interactive rebase performed via temporary todo file and GIT_SEQUENCE_EDITOR