# git-tidy

A tool to automate [parts of] complicated and tedious git operations, e.g. intelligently reordering git commits by grouping them based on file similarity.

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

# Preview or apply a safe merge with ort + rename detection
git-tidy smart-merge --branch feature/x --into main            # preview (no changes)
git-tidy smart-merge --branch feature/x --into main --apply    # apply merge

# Preview or apply strategy-assisted reverts
git-tidy smart-revert --commits abc123                         # preview (no changes)
git-tidy smart-revert --range main..HEAD --apply               # apply reverts

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

#### `smart-merge`
**Scenario**: You need to merge a feature branch into main but want to avoid common merge pitfalls like broken rename detection or poor conflict resolution.

**Effect**: Performs a safer merge using the ort strategy with rename detection, creating a clean merge commit with better conflict resolution than default git merge.

**Example scenarios**:
- Merging a feature branch that renamed/moved files
- Integrating changes from a long-running branch with potential conflicts
- Ensuring merge quality with automated testing before finalizing

**Key options**:
- `--branch BRANCH`, `--into TARGET`: Specify source and target branches
- `--apply`: Actually perform the merge (default is preview-only for safety)
- `--optimize-merge`: Temporarily enables safer git settings during merge
- `--conflict-bias=ours|theirs`: Auto-resolve conflicts favoring one side
- `--rename-detect`: Handle file renames intelligently (recommended)
- `--auto-resolve-trivial`: Skip manual intervention for obvious conflicts
- `--lint/--test/--build`: Run validation after merge to ensure quality

#### `smart-rebase`
**Scenario**: You need to rebase your feature branch onto an updated main branch but want to avoid the pain of resolving the same conflicts repeatedly or dealing with duplicate commits.

**Effect**: Performs an intelligent rebase that skips commits already present (via patch-id), handles conflicts better, and provides comprehensive safety nets and validation.

**Example scenarios**:
- Rebasing after main has been updated with related changes
- Cleaning up a messy feature branch before merging
- Handling complex rebases with many potential conflicts
- Ensuring your rebased branch still builds and passes tests

**Key options**:
- `--base BASE`: Target branch to rebase onto (e.g., origin/main)
- `--prompt`: Ask for confirmation before destructive operations (default: on)
- `--backup`: Create backup branch before starting (default: on, recommended)
- `--optimize-merge`: Use safer git settings during conflict resolution
- `--conflict-bias=ours|theirs`: Auto-resolve conflicts by favoring one side
- `--chunk-size N`: Process commits in smaller batches to isolate conflicts
- `--auto-resolve-trivial`: Skip manual intervention for obvious conflicts
- `--lint/--test/--build`: Validate each step to catch breakage early

#### `smart-revert`
**Scenario**: You need to undo problematic commits from your branch or main, but the commits involved file renames or complex changes that make standard `git revert` difficult.

**Effect**: Intelligently reverts commits using better merge strategies and rename detection, creating clean revert commits that properly undo the intended changes.

**Example scenarios**:
- Reverting a feature that broke production
- Undoing commits that renamed files before making other changes
- Rolling back a range of related commits cleanly
- Ensuring reverts don't break the build

**Key options**:
- `--commits SHA1,SHA2`: Revert specific commits by hash
- `--range A..B`: Revert all commits in a range
- `--count N`: Revert the last N commits
- `--apply`: Actually perform the revert (default is preview-only)
- `--conflict-bias=ours|theirs`: Auto-resolve conflicts during revert
- `--rename-detect`: Handle file renames properly during revert
- `--lint/--test/--build`: Validate that revert doesn't break anything

#### `rebase-skip-merged`
**Scenario**: You're rebasing a feature branch onto main, but some of your commits were already cherry-picked or merged into main through another branch, causing unnecessary conflicts or duplicate commits.

**Effect**: Rebases your branch while intelligently skipping commits that already exist on the target branch (detected via patch-id), avoiding duplicate commits and related conflicts.

**Example scenarios**:
- Your feature branch has commits that were hotfixed directly to main
- Another branch merged some of your changes before you could rebase
- You're syncing with a main branch that had commits cherry-picked from your work

**Key options**:
- `--base BASE`: Target branch to rebase onto
- `--prompt`: Confirm before starting the rebase operation
- `--backup`: Create backup branch (recommended for safety)
- `--optimize-merge`: Use safer git settings during rebase
- `--conflict-bias=ours|theirs`: Auto-resolve remaining conflicts

#### `configure-repo`
**Scenario**: You want to set up a repository with safer git defaults to reduce common merge and rebase problems before they happen.

**Effect**: Applies a curated set of git configuration settings that improve merge behavior, enable better rename detection, and set up helpful defaults.

**Example scenarios**:
- Setting up a new repository for team development
- Improving git behavior in an existing problematic repository
- Standardizing git settings across multiple repositories
- Enabling better merge strategies by default

**Key options**:
- `--scope local`: Apply settings only to current repository (recommended)
- `--scope global`: Apply settings to your global git configuration
- `--preset safe`: Use conservative, widely-compatible settings (default)

#### `group-commits`
**Scenario**: Your feature branch has commits that touch overlapping files in a scattered way, making the history hard to follow and potentially causing unnecessary merge conflicts.

**Effect**: Analyzes file overlap between commits and reorders them to group related changes together, making the commit history more logical and easier to review.

**Example scenarios**:
- Preparing a feature branch for code review with cleaner history
- Reducing potential conflicts by grouping related file changes
- Making it easier to cherry-pick or revert related changes together
- Cleaning up development commits before merging

**Key options**:
- `--base BASE`: Specify which commits to group (from base to HEAD)
- `--threshold FLOAT`: How similar files must be to group commits (0.0-1.0, default 0.3)
- `--dry-run`: Preview the grouping without making changes
- Lower threshold = more aggressive grouping, higher = more conservative

#### `split-commits`
**Scenario**: You have commits that change multiple unrelated files, making them hard to review, cherry-pick, or revert selectively.

**Effect**: Breaks down each multi-file commit into separate commits, one per file, preserving the original commit message but making changes more granular.

**Example scenarios**:
- Preparing commits for easier code review
- Enabling selective cherry-picking of specific file changes
- Making it easier to revert changes to individual files
- Converting large refactoring commits into reviewable pieces

**Key options**:
- `--base BASE`: Specify which commits to split (from base to HEAD)
- `--dry-run`: Preview the splitting without making changes
- Note: This creates many more commits, so use carefully

### Advanced/Utility
- `select-base`, `preflight-check`, `auto-continue`, `auto-resolve-trivial`, `range-diff-report`, `rerere-share`, `checkpoint-create`, `checkpoint-restore` — helper commands used by `smart-rebase` and available for advanced workflows.
- `select-reverts` — helper to list commit SHAs to revert using filters like `--range`, `--count`, `--grep`, `--author`.

## How it works

Git-tidy provides intelligent git operations through strategy-assisted merges, rebases, and reverts with safety features like automatic backups and conflict resolution. It uses advanced git strategies (ort with rename detection), patch-id awareness for deduplication, and file similarity analysis for commit grouping.

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
