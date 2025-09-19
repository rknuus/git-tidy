# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## For Claude
- Quality gate: After any code change, ensure all quality checks pass (`make ci-checks`).
- Primary documentation: Refer to [README.md](README.md) for usage, command reference, and examples.

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