---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# System Patterns

## Architectural shape

`git-tidy` is a **thin, two-layer Python CLI** wrapping the local `git` binary:

```
┌──────────────────────────┐
│ argparse (cli.py)        │  Parse → dispatch to cmd_* → call GitTidy method
├──────────────────────────┤
│ GitTidy class (core.py)  │  Algorithms + orchestration; subprocess to git
├──────────────────────────┤
│ git CLI                  │  All actual repository I/O
└──────────────────────────┘
```

- **No internal service boundaries**, no plugins, no DI. The two-file shape is deliberate.
- All git access goes through a single internal helper (`run_git`) — the chokepoint where logging, error wrapping, and dry-run gating belong.
- Errors raise `GitError` (a single project-defined exception) rather than bare `subprocess.CalledProcessError`.

## Recurring patterns

### Preview by default, mutate on opt-in

Every destructive subcommand has the same shape:

- Default: `--dry-run` / preview prints what *would* happen, no repo state changes.
- Opt-in: `--apply` (for merge/revert) or implicit-action-on-confirmation (for rebase variants).
- Implementation: in `cli.py`, the `cmd_*` function branches on `args.dry_run`/`args.apply` and either calls a "show me the analysis" code path or the mutating method on `GitTidy`.

### Backup-before-mutate

History-rewriting commands create a backup branch before mutating:

- Naming convention: `backup-<shortsha>` (documented in `CLAUDE.md`).
- The smart-rebase code paths use this; new history-editing flows should follow the same convention.
- On failure, the original HEAD is restored from the backup.

### Tri-state flags via explicit enums

When a flag has more than two meaningful values, the CLI uses an enum string rather than overloading boolean semantics:

- `--conflict-bias=ours|theirs|none` — not `--prefer-ours/--prefer-theirs`.
- Booleans use `--[no-]flag`: `--prompt`/`--no-prompt`, `--rename-detect`/`--no-rename-detect`.

This keeps non-interactive scripted use predictable and avoids ambiguous default behavior.

### Validation hooks

The smart-* commands accept `--lint`, `--test`, `--build` flags. After each step (or at the end, depending on the command), the corresponding validation runs and a failure rolls back. This makes the commands suitable for unattended CI use without giving up safety.

### Patch-id awareness

`rebase-skip-merged` and `smart-rebase` use `git patch-id` to detect commits whose effect is already present on the target, so they can be skipped silently rather than producing "empty commit" pauses or duplicate commits. This is the central trick that makes rebasing onto a moving base usable on real branches.

### File-similarity grouping (Jaccard-style)

`group-commits` computes the file-set overlap between commits and clusters them with a tunable `--threshold` (default 0.3). This is purely a reordering — no commit content is altered. The algorithm lives in `GitTidy.group_commits`.

### Subprocess-only I/O

All actual git work shells out via `run_git`. There is no `pygit2` import in `src/` — `pygit2` is dev-only, used by tests to build fixture repositories.

Reasons:
- Zero runtime dependencies and easy distribution.
- Behavior matches user expectations (the same `git` binary they would invoke manually).
- Testing can use scripted fixture repos to assert real command behavior.

## Data flow (typical mutating command)

1. CLI parses args, instantiates `GitTidy()`.
2. `GitTidy.<method>` runs preflight checks (clean working tree, base reachable, etc.).
3. Backup branch created if the command rewrites history.
4. Operation executes in steps, each gated by `run_git`.
5. Optional validation hooks run.
6. On any error: rollback to backup, raise `GitError`.
7. CLI formats the error and exits non-zero.

## Test architecture mirrors this

- Unit tests target `GitTidy` methods directly with mocked or real git.
- Fixture tests build repositories with `pygit2` to set up realistic preconditions.
- System tests invoke the real CLI via `tests/system/framework/git_tidy_runner.py` and assert on resulting repo state via `result_validator.py`.

The three tiers correspond directly to the three layers in the architecture diagram above.
