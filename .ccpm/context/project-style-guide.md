---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# Project Style Guide

## Authoritative tooling

These tools own style decisions; do not redo their work by hand:

- **black** — line length 88, target py39. `make format`, `make format-check`.
- **ruff** — rule sets `E, W, F, I, B, C4, UP`; `E501` ignored (black owns line length). `make lint`, `make lint-fix`.
- **mypy** — strict: `disallow_untyped_defs`, `disallow_incomplete_defs`, `warn_unused_ignores`, `no_implicit_optional`, `warn_redundant_casts`, `warn_unreachable`. `make typecheck`.

Run `make quality-fix` before committing to apply auto-fixable changes; `make ci-checks` to validate.

## Type annotations

- **Mandatory** for every function and method in `src/`. Mypy strict will reject untyped defs.
- Tests are not exempt by configuration — write annotations there too.
- Prefer `from __future__ import annotations` only when needed for forward references; the py39 baseline allows most modern syntax without it.

## CLI flag conventions (project-specific, enforced by review)

- **Booleans**: `--[no-]flag` shape. Example: `--prompt` / `--no-prompt`, `--rename-detect` / `--no-rename-detect`.
- **Tri-state and beyond**: explicit enum strings. Example: `--conflict-bias=ours|theirs|none`. Never overload `--prefer-x` booleans for what is conceptually an enum.
- **Apply vs preview**: destructive commands default to preview/dry-run; `--apply` opts in to mutation.

These conventions are documented in `CLAUDE.md` and are part of the project's contract with scripted users.

## Naming

- **Modules**: lower_snake (`cli.py`, `core.py`).
- **Classes**: `PascalCase` — `GitTidy`, `GitError`.
- **Functions / methods**: `lower_snake`. CLI dispatch functions follow `cmd_<subcommand>` (e.g., `cmd_group_commits`, `cmd_split_commits`). Algorithm methods describe the operation: `group_commits`, `split_commits`, `smart_merge`.
- **Constants**: `UPPER_SNAKE` if introduced.
- **Test functions**: `test_<unit-of-behavior>` (pytest convention).
- **Backup branches**: `backup-<shortsha>` (literal convention for the tool's own outputs).

## Imports and layout

- ruff's isort rule (`I`) enforces import order: stdlib → third-party → local, alphabetized within groups.
- Re-exports from a subpackage `__init__.py` are explicit (`__all__`) — see `src/git_tidy/__init__.py` for the pattern: re-export `GitTidy`, `GitError`; declare `__version__`.

## Error handling

- Raise `GitError` (defined in `core.py`, re-exported from the package root) for git-operation failures. Wrap subprocess errors with context — never let `CalledProcessError` propagate from public methods.
- Validation hook failures (`--lint`, `--test`, `--build`) trigger rollback to backup before propagating an error.

## Tests

- Pytest, with markers `fast`, `slow`, `conflicts` declared in `pyproject.toml`. `--strict-markers` is enforced — register new markers in `pyproject.toml`, do not introduce ad-hoc ones.
- System tests use the framework in `tests/system/framework/` (`git_tidy_runner.py`, `result_validator.py`). New end-to-end tests should go through this framework, not invoke subprocess directly.
- Fixture repositories are built with `pygit2`. Keep fixtures self-contained and deterministic; no network access in tests.
- Slow tests must be marked `@pytest.mark.slow` so the default `make system-tests-fast` flow stays quick.

## Documentation

- **README.md is canonical** for user-facing command and flag documentation. CLAUDE.md is intentionally minimal and points back to the README.
- When adding/changing a CLI flag or command, update `README.md` (Core Commands + Examples) and add/adjust tests. This is part of the project's documentation contract (see CLAUDE.md).
- Module/function docstrings: short, single-purpose. Multi-paragraph docstrings are not project style.

## Comments

- Default to no comments. Add a comment only when the reason for the code is non-obvious from the names — a hidden invariant, a workaround for a specific git quirk, etc.
- Do not narrate what the code does ("loop over commits") — names should already make that clear.

## Commit hygiene

- Use the conventional-style prefixes already present in history: `feat:`, `fix:`, `doc:`, `test:`. Stay consistent.
- Per CLAUDE.md: prefer creating new commits over amending; never `--no-verify` to skip hooks.
