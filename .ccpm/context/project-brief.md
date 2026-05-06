---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# Project Brief

## Core purpose

Reduce the cognitive load and risk of routine-but-tricky git history operations — merges, rebases, reverts, and commit reorganization — by codifying battle-tested strategies (rename-detecting `ort`, patch-id deduplication, backups, validation hooks) into preview-first CLI subcommands.

## Goals

1. **Make destructive history operations safe to attempt.** Default to dry-run/preview; require explicit `--apply`. Always create a backup branch before mutating history. Restore on failure.
2. **Eliminate repeat conflict resolution.** Patch-id-aware skip of already-merged content; tri-state conflict bias; integration with `rerere`.
3. **Improve the readability of in-progress branches.** File-similarity-based commit grouping and per-file splitting produce histories that are easier to review and selectively revert.
4. **Stay zero-runtime-dep and portable.** Python ≥ 3.9, standard library only at runtime, shells out to `git`. No vendor-locked services or hosted dependencies.
5. **Be CI-friendly and non-interactive by default in scripted contexts.** Boolean flags use `--[no-]flag`; tri-state options use explicit enums; `--prompt`/`--no-prompt` controls interactivity.

## Success criteria

- A user can preview the effect of any destructive command without touching the working tree.
- After any failed apply, the repository is left in its original state (backup branch present, HEAD restored).
- `make ci-checks` (ruff + mypy strict + black --check + pytest) is green on every commit to `main`.
- System tests cover the realistic scenarios (configure-repo, group-commits, split-commits, smart-merge, end-to-end integration) against scripted fixture repositories.
- A new contributor can run `make dev-setup && make ci-checks` and have a working environment without manual intervention.

## Scope boundaries

- **In scope**: Local git history operations and configuration. Authoring the CLI surface, safety machinery, and validation hooks.
- **Out of scope**: Remote operations (push/pull) and force-pushing — never invoked unless the user explicitly requests them; no implicit network calls. Hosted services, GUIs, and IDE plugins.
