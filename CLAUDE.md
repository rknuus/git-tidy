# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## For Claude
- Quality gate: After any code change, ensure all quality checks pass (`make ci-checks`).
- Primary documentation: Refer to [README.md](README.md) for usage, command reference, and examples.

- Safety rules for git operations:
  - Default to dry-run for destructive/history-editing commands unless explicitly requested otherwise.
  - Always create a backup branch before history edits; follow the `backup-<shortsha>` convention already used in core.
  - Never force-push or interact with remotes (push/pull) unless explicitly requested.
  - Do not modify the repo state during tests/examples; prefer dry-run or operate on a temporary branch.

- Non-interactive execution:
  - Prefer non-interactive flags and fail fast; do not rely on prompts in automated runs.
  - Use Make targets and `uv` (e.g., `uv run ...`) for a consistent environment.

- CLI flag conventions:
  - Booleans use `--[no-]flag` (e.g., `--prompt`/`--no-prompt`).
  - Tri-state behavior uses explicit enums (e.g., `--conflict-bias=ours|theirs|none`).

- Coding and quality gates:
  - Enforced styles: black (88), ruff (configured in `pyproject.toml`), mypy (no untyped defs).
  - Always run `make ci-checks` before and after edits; all tests must pass.

## Quick Pointers
- Entry points:
  - CLI: `src/git_tidy/cli.py`
  - Core: `src/git_tidy/core.py`
  - Tests: `tests/`
- Development:
  - `make help` shows useful targets
  - `make dev-setup` to set up the environment
  - `make quality-checks` / `make quality-fix` for lint/type/format
  - `make test` for the full test suite

## Where to find details
- Commands and options (including `smart-rebase`, `rebase-skip-merged`, `configure-repo`): see [README.md](README.md) “Usage”, “Core Commands”, and examples.
- Architecture overview and safety features: see [README.md](README.md) “How it works” and “Safety Features”.

## Notes
- This project uses only the Python standard library plus git CLI.
- Keep import order and formatting compliant with ruff/black; run `make quality-fix` if needed.
- Scope of commands:
  - "Smart" commands (`smart-rebase`, `rebase-skip-merged`) change history; require clear user intent or `--prompt` enabled.
  - Prefer local scope by default; `configure-repo` should default to `--scope local` unless requested.

- Documentation contract:
  - If adding/updating CLI flags or commands, update README (Core Commands/Examples) and adjust/add tests accordingly.
  - Keep this file minimal; treat README as the canonical reference.

- Environment assumptions:
  - Python ≥ 3.9 (CI uses 3.12), git CLI available.
  - Use `uv` for development tasks and `hatchling` for builds.