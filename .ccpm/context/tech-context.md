---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# Technical Context

## Language and runtime

- **Python** ≥ 3.9 (CI uses 3.12). Targets py39 syntax floor.
- **`git` CLI** must be available on `PATH` — all git operations are subprocess calls.
- **No third-party runtime dependencies.** Standard library only.

## Dependencies

Declared in `pyproject.toml`:

- **Runtime**: `dependencies = []` — empty by design.
- **Dev (`[dependency-groups].dev` and `[project.optional-dependencies].dev`)**:
  - `pytest >= 8.3.5` — test runner
  - `pytest-cov >= 6.0.0` — coverage
  - `pytest-xdist >= 3.0.0` — parallel test execution (used by `make system-tests-parallel`)
  - `pygit2 >= 1.15.0` — used in test fixtures to build/manipulate repository scenarios
  - `ruff >= 0.13.0` — linter (configured in `[tool.ruff]`)
  - `black >= 22.0` — formatter, line length 88, target py39
  - `mypy >= 1.14.1` — type checker, **strict mode**: `disallow_untyped_defs`, `disallow_incomplete_defs`, `warn_unused_ignores`, etc.

## Build system

- **`hatchling`** as the build backend. Packages from `src/git_tidy`.
- **`uv`** as the dependency manager and task runner of choice. `uv.lock` is checked in.
- Source distribution includes `/src`, `/tests`, `README.md`, `CLAUDE.md`.
- Entry point: `git-tidy = "git_tidy.cli:main"`.

## Quality and tooling configuration

- **Ruff**: `select = ["E", "W", "F", "I", "B", "C4", "UP"]`; `ignore = ["E501"]` (line length owned by black).
- **Black**: `line-length = 88`, `target-version = ["py39"]`.
- **Mypy**: strict — see `[tool.mypy]` for the full set; type definitions are mandatory throughout `src/`.
- **Pytest**: `testpaths = ["tests"]`; markers `fast`, `slow`, `conflicts`; `--strict-markers --strict-config -ra` enforced.
- **Coverage**: source `["src"]`, omits tests; `pragma: no cover` and abstract methods excluded from reporting.

## Repository conventions (from `CLAUDE.md`)

- Always run `make ci-checks` before and after edits.
- CLI flag style:
  - Booleans → `--[no-]flag` (e.g., `--prompt` / `--no-prompt`).
  - Tri-state → explicit enums (e.g., `--conflict-bias=ours|theirs|none`).
- Safety rules for git operations:
  - Default to dry-run for destructive/history-editing commands.
  - Always create a backup branch (`backup-<shortsha>` convention) before history edits.
  - Never force-push or interact with remotes unless explicitly requested.
  - Never modify repo state during tests/examples; prefer dry-run or temporary branches.

## Make targets (most-used)

- `make dev-setup` — `uv sync --dev`.
- `make quality-checks` — `lint + typecheck + format-check`.
- `make quality-fix` — `lint-fix + format`.
- `make test` — `uv run pytest`.
- `make system-tests-{fast,full,parallel,coverage}` — system test variants.
- `make ci-checks` — `quality-checks + test` (canonical pre-commit gate).
- `make build` / `make build-check` / `make publish[-test]` — distribution.

## Distribution

- Built artifacts in `dist/` (sdist + wheel). Published to PyPI via `twine` (`make publish` requires interactive confirmation).
