---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# Project Structure

## Top-level layout

```
git-tidy/
├── src/git_tidy/           # Package source (the only thing shipped)
│   ├── __init__.py         # Re-exports GitTidy, GitError; sets __version__
│   ├── cli.py              # argparse-based CLI; one cmd_* function per subcommand
│   └── core.py             # GitTidy class — all git operations and algorithms
├── tests/                  # Pytest test suites
│   ├── test_cli.py
│   ├── test_core.py
│   ├── test_integration.py
│   ├── test_repository_fixtures.py
│   ├── test_advanced_repository_fixtures.py
│   ├── test_repository_integration.py
│   └── system/             # End-to-end scenarios against fixture repos
│       ├── framework/      # Reusable test harness
│       │   ├── git_tidy_runner.py
│       │   └── result_validator.py
│       ├── test_configure_repo.py
│       ├── test_group_commits.py
│       ├── test_smart_merge.py
│       ├── test_split_commits.py
│       └── test_system_integration.py
├── pyproject.toml          # Build, deps, tool configuration (single source of truth)
├── uv.lock                 # uv-managed lockfile
├── Makefile                # Developer-facing task runner
├── README.md               # Canonical usage and command reference
├── CLAUDE.md               # Claude Code project instructions
├── LICENSE                 # GPL-3.0
└── .claude/                # Local Claude Code config (untracked)
```

## Module organization

The package is **two files**: `cli.py` and `core.py`. There is intentionally no further internal package structure.

### `core.py` (~1230 lines)

The `GitTidy` class is the engine. Public entry points include:

- **Commit inspection**: `get_commits_to_rebase(base)`, `describe_group(group)`.
- **Rebase orchestration**: `run(base, threshold, no_prompt)` — the `group-commits` end-to-end.
- **Grouping algorithm**: `group_commits(commits, threshold)` — file-similarity clustering.
- **Splitting**: `split_commits(base, no_prompt)` — per-file commit decomposition.
- **Smart commands**: `smart_merge(...)`, `smart_revert(...)`, `smart_rebase(...)`, `rebase_skip_merged(...)`.
- **Configuration**: `configure_repo(scope, preset)`.
- **Helpers used by smart commands**: select-base, preflight-check, auto-continue, auto-resolve-trivial, range-diff-report, rerere-share, checkpoint-create/restore, select-reverts.
- **Subprocess shim**: `run_git(args)` — every git invocation goes through here.
- **Error type**: `GitError` (re-exported via `__init__.py`).

### `cli.py` (~989 lines)

Pure argparse plumbing. Each subcommand has a `cmd_<name>(args)` function that:

1. Instantiates `GitTidy()`.
2. Branches on `args.dry_run` / `args.apply` to choose preview vs mutating path.
3. Delegates to a `GitTidy` method.

`main()` builds the parser, registers subparsers, and dispatches.

## Test layout

- **Unit-ish** (`tests/test_core.py`, `tests/test_cli.py`): exercise `GitTidy` methods and CLI argument handling directly.
- **Fixture-based** (`tests/test_repository_fixtures.py`, `test_advanced_repository_fixtures.py`, `test_repository_integration.py`): construct repositories using `pygit2` to test against realistic histories.
- **Integration** (`tests/test_integration.py`): glue between CLI and core.
- **System** (`tests/system/`): the most behavioral tier. The `framework/` subpackage owns:
  - `git_tidy_runner.py` — invokes the installed CLI as a subprocess.
  - `result_validator.py` — asserts on resulting repository state.

  Each `test_*.py` under `tests/system/` covers one subcommand or end-to-end flow and uses the framework rather than touching subprocess directly.

## Key files for navigation

- Entry to all commands: `src/git_tidy/cli.py:main()`.
- Algorithmic core: `src/git_tidy/core.py` — `GitTidy` class.
- Test framework: `tests/system/framework/git_tidy_runner.py`.
- Build/config truth: `pyproject.toml`.
- Developer commands: `Makefile`.
- Project rules for Claude: `CLAUDE.md`.
