---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# Project Overview

`git-tidy` is a Python CLI that automates parts of complicated, error-prone git history operations. It wraps the `git` command-line tool with safer defaults, strategy-assisted merges/rebases/reverts, file-similarity-based commit grouping, per-file commit splitting, and curated repository configuration.

## What it does

The tool exposes a single `git-tidy` command with several subcommands. Each subcommand targets a recurring pain point in everyday git workflows:

- **`smart-merge`** — Merge a branch with the `ort` strategy + rename detection, optional auto-resolution biases, and post-merge lint/test/build validation. Defaults to preview mode; `--apply` performs the merge.
- **`smart-rebase`** — Orchestrated rebase onto a base with patch-id-aware deduplication, automatic backup branches, optional chunked execution to isolate conflicts, and post-step validation hooks.
- **`smart-revert`** — Revert specific SHAs, ranges, or "last N" commits using rename detection and conflict-bias hints. Preview-by-default with `--apply` opt-in.
- **`rebase-skip-merged`** — Rebase variant that drops commits already present on the target via patch-id matching, eliminating duplicate-commit churn.
- **`configure-repo`** — Apply a curated preset of safer git config (e.g., better merge strategy defaults). Local scope by default.
- **`group-commits`** — Reorder commits in a range so that those touching similar files cluster together, using a configurable similarity threshold (Jaccard-style on file sets).
- **`split-commits`** — Decompose multi-file commits into one-commit-per-file, preserving the original message.
- **Helpers**: `select-base`, `preflight-check`, `auto-continue`, `auto-resolve-trivial`, `range-diff-report`, `rerere-share`, `checkpoint-create/restore`, `select-reverts`. These are building blocks of the smart commands and are also usable directly for advanced workflows.

## Key features

- **Safety-first defaults**: dry-run/preview by default for destructive commands; explicit `--apply` to mutate.
- **Automatic backup branches** before history rewrites (named `backup-<shortsha>`).
- **Tri-state conflict bias** via `--conflict-bias=ours|theirs|none` and toggleable booleans via `--[no-]flag` conventions.
- **Validation hooks** (`--lint/--test/--build`) executed after operations to catch breakage early.
- **Patch-id-based deduplication** to avoid redundant commits on already-merged content.
- **Pure standard library** runtime (no third-party runtime deps); shells out to the local `git` CLI.

## Integration points

- **Git CLI**: All git operations are subprocess calls to `git`. The tool does not embed libgit2 at runtime (though `pygit2` is used in dev for richer test fixtures).
- **Shell environment**: Distributed as a Python package; entry point `git-tidy` registered in `pyproject.toml`.
- **CI/Quality stack**: `make ci-checks` runs lint (`ruff`), type checks (`mypy --strict`), format check (`black`), and `pytest` unit/integration/system tests.
