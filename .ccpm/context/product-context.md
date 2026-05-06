---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# Product Context

## Target users

- **Working software engineers** who use git daily and have hit the recurring pain points the smart commands address: rebase onto a moving base, repeated conflict resolution, accidental duplicate commits from cherry-picks, hard-to-review feature branches.
- **Tech leads / maintainers** standardizing git behavior across a team via `configure-repo` presets.
- **CI authors** who need scripted, non-interactive history operations with safe defaults and validation hooks.

The tool assumes the user is comfortable on the git CLI. It is not a beginner aid — it is a force multiplier for people who already know what they want git to do but find the manual incantations error-prone.

## Use cases

### "I'm about to rebase a long-running feature branch onto a moved main."

→ `git-tidy smart-rebase --base origin/main --prompt --optimize-merge`

Auto-creates backup, uses `ort` + rename detection, prompts before destructive steps, can chunk to isolate conflict zones, optionally runs lint/test/build between chunks.

### "Some of my commits got cherry-picked into main and now my rebase wants to redo them."

→ `git-tidy rebase-skip-merged --base origin/main --no-prompt`

Patch-id detection skips already-applied commits silently.

### "I need to revert this feature, but it touched renames."

→ `git-tidy smart-revert --commits abc123 --rename-detect`

### "My feature branch is messy — same files touched in non-adjacent commits."

→ `git-tidy group-commits --dry-run` (preview), then without `--dry-run` to apply.

### "I want to break a refactor commit into one-per-file pieces for review."

→ `git-tidy split-commits --base origin/main`

### "New repo, I want sane git defaults."

→ `git-tidy configure-repo --scope local --preset safe`

## Constraints and design tensions

### Safety > convenience

Every destructive command defaults to preview/dry-run. This adds a step compared to native git, but the explicit `--apply` step is intentional friction. Users who want fast unattended runs use `--no-prompt` plus `--apply` knowingly.

### Local-only by default

The tool does not push, pull, or fetch unless the user explicitly invokes a flow that requires it. CLAUDE.md codifies this: "Never force-push or interact with remotes (push/pull) unless explicitly requested." This is both a UX choice (no surprise network I/O) and a security choice.

### Zero runtime deps

A user installs `git-tidy` and gets the standard library. No transitive risk. Trade-off: anything fancier than subprocess (e.g., reading object DB directly) is unavailable at runtime — but the system tests prove subprocess is sufficient.

### Scripted contexts must be predictable

CLI flag conventions are non-negotiable: `--[no-]flag` for booleans, explicit enums for tri-state. This is what makes the tool safe to embed in CI without prompts.

## Domain concepts

- **Backup branch (`backup-<shortsha>`)**: a pointer to the original HEAD created before any history rewrite, used for rollback.
- **Conflict bias**: a hint to git's merge machinery about which side to prefer when otherwise indistinguishable: `ours`, `theirs`, or `none` (let conflicts surface).
- **Patch-id**: a content-derived identifier (`git patch-id`) that lets the tool detect "this commit's effect is already on the target" even when SHAs differ.
- **Smart command**: any `smart-*` subcommand — these are orchestrated wrappers that bundle backup + strategy + validation + recovery around a primitive git operation.
- **Threshold (group-commits)**: float in `[0.0, 1.0]`, the minimum file-set similarity for two commits to be grouped. Lower = more aggressive grouping.
- **Optimize-merge mode**: temporarily applies safer git config (rename detection, conflict markers, etc.) for the duration of the operation.
