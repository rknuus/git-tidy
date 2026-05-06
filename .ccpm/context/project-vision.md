---
created: 2026-05-06T17:27:27Z
last_updated: 2026-05-06T17:27:27Z
version: 1.0
author: Claude Code PM System
---

# Project Vision

## Long-term direction

Become the default "I want to do this git operation safely" wrapper for engineers who have outgrown raw `git` for routine history work but do not want a heavyweight GUI or hosted service.

The tool's identity is built on three ideas that should remain stable as it grows:

1. **Preview-first, then apply.** Every destructive operation lets the user see the outcome before committing to it. No exceptions.
2. **Local-only, zero runtime deps.** A working `git` binary and Python are the only requirements. No PyPI dependencies pulled in at runtime, no implicit network calls, no hosted service.
3. **Scripts and humans, equally.** Flag conventions (`--[no-]flag`, enum tri-state, `--prompt`/`--no-prompt`) make every command usable both interactively and from CI without surprises.

## Roadmap themes (no fixed dates)

### Hardening (current focus)

- Continue closing gaps surfaced by the system test suite (`tests/system/`). Recent commits show this is the active workstream — fixes from system tests landed in `a2ed0ea` and `7d2747a`, with `28da1b9` adding the missing parallel-test dependency.
- Promote `Development Status` from `3 - Alpha` toward beta once system-test coverage stabilizes across all smart-* commands.
- Strengthen rollback machinery: ensure backup-and-restore is invariant across every history-rewriting code path.

### Surface refinement

- Smooth the user-facing flag set across smart-merge, smart-rebase, smart-revert so that conventions match across commands (e.g., uniform `--apply`, `--conflict-bias`, validation-hook flags).
- Improve preview output quality: dry-run output should be precise enough to stand in as a code-review artifact for the proposed history change.

### Workflow extensions

- Possible additions over time, gated by demand: smart-cherry-pick, smart-bisect orchestration, conflict-resolution recipe sharing via `rerere-share`.
- Resist scope creep into things that are not history operations — issue tracking, PR creation, hosted services. Those belong in other tools.

## Strategic guardrails

These are constraints to preserve, not goals to achieve:

- **Never force-push or interact with remotes implicitly.** Codified in CLAUDE.md and reinforced by behavior: the tool does not call `git push`/`pull`/`fetch` unless the user explicitly invokes a flow that requires it.
- **Never break the zero-runtime-dependency property.** Adding a runtime dep would change the install story and the trust calculus. If a feature seems to require one, find another way or rethink the feature.
- **Never make safety opt-in.** Backups, dry-run defaults, and validation hooks must remain the default posture; convenience flags can opt out, but the defaults stay safe.
- **Keep the package small.** Two-file core (`cli.py` + `core.py`) is intentional. Resist premature subpackage carving until at least one of the files crosses the point where its single-file shape is actively impeding work.

## What success looks like

- Engineers in scripted CI environments use `git-tidy` for rebase/merge/revert and trust the dry-run output enough to run unattended applies.
- A new contributor can `make dev-setup && make ci-checks` and have a fully working environment within minutes — no manual config of git hooks, no third-party services to register.
- The tool gets out of the way: when it works, it is invisible; when it can't proceed safely, it stops and explains why with a backup already in place.
