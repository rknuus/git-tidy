"""Command-line interface for git-tidy."""

import argparse
import sys

from .core import GitTidy


def cmd_group_commits(args: argparse.Namespace) -> None:
    """Handle the group-commits subcommand."""
    git_tidy = GitTidy()

    if args.dry_run:
        # Just show the analysis
        commits = git_tidy.get_commits_to_rebase(args.base)
        groups = git_tidy.group_commits(commits, args.threshold)

        print(f"Found {len(commits)} commits, would group into {len(groups)} groups:")
        for i, group in enumerate(groups):
            print(f"\nGroup {i + 1} ({len(group)} commits):")
            print(f"  Files: {git_tidy.describe_group(group)}")
            for commit in group:
                print(f"    {commit['sha'][:8]} {commit['subject']}")
    else:
        git_tidy.run(
            args.base, args.threshold, no_prompt=getattr(args, "no_prompt", False)
        )


def cmd_split_commits(args: argparse.Namespace) -> None:
    """Handle the split-commits subcommand."""
    git_tidy = GitTidy()

    if args.dry_run:
        # Just show the analysis
        commits = git_tidy.get_commits_to_rebase(args.base)
        print(f"Found {len(commits)} commits to split:")
        for commit in commits:
            print(f"\nCommit {commit['sha'][:8]}: {commit['subject']}")
            print(
                f"  Files ({len(commit['files'])}): {', '.join(sorted(commit['files']))}"
            )
            print(f"  Would create {len(commit['files'])} separate commits:")
            for file in sorted(commit["files"]):
                print(f"    - split off {file}")
    else:
        git_tidy.split_commits(args.base, no_prompt=getattr(args, "no_prompt", False))


def cmd_squash_all(args: argparse.Namespace) -> None:
    """Handle the squash-all subcommand."""
    git_tidy = GitTidy()

    # Get commits to squash
    commits = git_tidy.get_commits_to_rebase(args.base)

    if not commits:
        print("No commits found to squash")
        return

    # Get base commit
    first_commit_sha = commits[0]["sha"]
    base_commit = git_tidy.run_git(["rev-parse", f"{first_commit_sha}^"]).stdout.strip()

    print(f"Found {len(commits)} commits to squash:")
    for commit in commits:
        print(f"  {commit['sha'][:8]} {commit['subject']}")

    print("\nTo squash all commits into one, run these commands:")
    print(f"  git reset --soft {base_commit[:8]}")
    print('  git commit -m "Your new commit message"')
    print("\nThis will:")
    print(f"  - Reset to commit {base_commit[:8]} (keeping all changes staged)")
    print("  - Allow you to create a single commit with all changes")
    print(f"  - Combine {len(commits)} commits into 1 commit")


def cmd_configure_repo(args: argparse.Namespace) -> None:
    """Handle the configure-repo subcommand."""
    git_tidy = GitTidy()

    options = {
        "scope": args.scope,
        "preset": args.preset,
        "enable": args.enable or [],
        "disable": args.disable or [],
        "lockfile_policy": args.lockfile_policy,
        "dry_run": args.dry_run,
        "no_prompt": args.no_prompt,
        "backup_path": args.backup_path,
        "undo": args.undo,
    }

    git_tidy.configure_repo(options)


def cmd_rebase_skip_merged(args: argparse.Namespace) -> None:
    """Handle the rebase-skip-merged subcommand."""
    git_tidy = GitTidy()

    options = {
        "base": args.base,
        "branch": args.branch,
        "prompt": args.prompt,
        "backup": args.backup,
        "dry_run": args.dry_run,
        "resume_from": args.resume_from,
        "chunk_size": args.chunk_size,
        "by_groups": args.by_groups,
        "max_conflicts": args.max_conflicts,
        "optimize_merge": args.optimize_merge,
        "conflict_bias": args.conflict_bias,
        "rerere_cache": args.rerere_cache,
        "use_rerere_cache": args.use_rerere_cache,
        "auto_resolve_trivial": args.auto_resolve_trivial,
        "rename_detect": args.rename_detect,
        "lint": args.lint,
        "test": args.test,
        "build": args.build,
        "report": args.report,
        "summary": args.summary,
    }

    git_tidy.rebase_skip_merged(options)


def cmd_preflight_check(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    options = {
        "base": args.base,
        "branch": args.branch,
        "allow_dirty": args.allow_dirty,
        "allow_wip": args.allow_wip,
        "dry_run": args.dry_run,
    }
    git_tidy.preflight_check(options)


def cmd_select_base(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    options = {"preferred": args.preferred, "fallback": args.fallback}
    base = git_tidy.select_base(options)
    print(base)


def cmd_auto_continue(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    git_tidy.auto_continue()


def cmd_auto_resolve_trivial(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    git_tidy.auto_resolve_trivial()


def cmd_chunked_replay(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    commits = args.commits.split(",") if args.commits else []
    options = {"base": args.base, "commits": commits, "chunk_size": args.chunk_size}
    git_tidy.chunked_replay(options)


def cmd_range_diff_report(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    git_tidy.range_diff_report(args.old, args.new)


def cmd_validate(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    options = {
        "lint": args.lint,
        "test": args.test,
        "build": args.build,
    }
    git_tidy.validate(options)


def cmd_rerere_share(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    options = {"action": args.action, "path": args.path}
    git_tidy.rerere_share(options)


def cmd_checkpoint_create(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    git_tidy.create_backup()


def cmd_checkpoint_restore(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    git_tidy.restore_from_backup()


def cmd_smart_rebase(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    options = {
        "branch": args.branch,
        "base": args.base,
        "prompt": args.prompt,
        "backup": args.backup,
        "dry_run": args.dry_run,
        "optimize_merge": args.optimize_merge,
        "conflict_bias": args.conflict_bias,
        "chunk_size": args.chunk_size,
        "auto_resolve_trivial": args.auto_resolve_trivial,
        "max_conflicts": args.max_conflicts,
        "rename_detect": args.rename_detect,
        "lint": args.lint,
        "test": args.test,
        "build": args.build,
        "report": args.report,
        "summary": args.summary,
        "skip_merged": args.skip_merged,
    }
    git_tidy.smart_rebase(options)


def cmd_smart_merge(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    options = {
        "branch": args.branch,
        "into": args.into,
        "apply": args.apply,
        "prompt": args.prompt,
        "backup": args.backup,
        "optimize_merge": args.optimize_merge,
        "conflict_bias": args.conflict_bias,
        "rename_detect": args.rename_detect,
        "rename_threshold": args.rename_threshold,
        "auto_resolve_trivial": args.auto_resolve_trivial,
        "max_conflicts": args.max_conflicts,
        "lint": args.lint,
        "test": args.test,
        "build": args.build,
        "report": args.report,
    }
    git_tidy.smart_merge(options)


def cmd_smart_revert(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    # normalize commits list (support comma-separated and multiple occurrences)
    commits: list[str] = []
    if args.commits:
        for item in args.commits:
            commits.extend([c for c in item.split(",") if c])
    options = {
        "commits": commits,
        "range": args.range,
        "count": args.count,
        "apply": args.apply,
        "prompt": args.prompt,
        "backup": args.backup,
        "optimize_merge": args.optimize_merge,
        "conflict_bias": args.conflict_bias,
        "rename_detect": args.rename_detect,
        "rename_threshold": args.rename_threshold,
        "auto_resolve_trivial": args.auto_resolve_trivial,
        "max_conflicts": args.max_conflicts,
        "lint": args.lint,
        "test": args.test,
        "build": args.build,
        "report": args.report,
    }
    git_tidy.smart_revert(options)


def cmd_select_reverts(args: argparse.Namespace) -> None:
    git_tidy = GitTidy()
    options = {
        "range": args.range,
        "count": args.count,
        "grep": args.grep,
        "author": args.author,
    }
    shas = git_tidy.select_reverts(options)
    for sha in shas:
        print(sha)


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="git-tidy",
        description="Tools for tidying up git commits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  git-tidy group-commits --dry-run
  git-tidy group-commits --threshold 0.5
  git-tidy group-commits --base origin/main
  git-tidy split-commits --dry-run
  git-tidy split-commits --base origin/main
  git-tidy squash-all --base origin/main
        """.strip(),
    )

    # Add version argument
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Create subparsers
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", metavar="COMMAND"
    )

    # group-commits subcommand
    group_parser = subparsers.add_parser(
        "group-commits",
        help="Group commits by file similarity and reorder them",
        description="Intelligently reorder git commits by grouping them based on file similarity.",
    )
    group_parser.add_argument(
        "--base",
        help="Base commit/branch for rebase range (defaults to merge-base with main/master)",
    )
    group_parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Similarity threshold (0.0-1.0, default: 0.3)",
    )
    group_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed grouping without performing rebase",
    )
    group_parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Proceed without prompting for confirmation",
    )
    group_parser.set_defaults(func=cmd_group_commits)

    # split-commits subcommand
    split_parser = subparsers.add_parser(
        "split-commits",
        help="Split each commit into separate commits, one per file",
        description="Split commits from base to HEAD into separate commits, one per file. Each new commit will have the message 'split off <file>' followed by the original commit message.",
    )
    split_parser.add_argument(
        "--base",
        help="Base commit/branch for rebase range (defaults to merge-base with main/master)",
    )
    split_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed splitting without performing rebase",
    )
    split_parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Proceed without prompting for confirmation",
    )
    split_parser.set_defaults(func=cmd_split_commits)

    # squash-all subcommand
    squash_parser = subparsers.add_parser(
        "squash-all",
        help="Show instructions to squash all commits into one",
        description="Show git commands to squash all commits from base to HEAD into a single commit. This is useful for reducing merge conflicts by combining multiple commits.",
    )
    squash_parser.add_argument(
        "--base",
        help="Base commit/branch for squash range (defaults to merge-base with main/master)",
    )
    squash_parser.set_defaults(func=cmd_squash_all)

    # configure-repo subcommand
    configure_parser = subparsers.add_parser(
        "configure-repo",
        help="Configure repository settings to reduce merge/rebase pain",
        description=(
            "Enable helpful git settings (rerere, zdiff3, patience, rename detection, "
            "safer rebases) and optional policies. Idempotent and safe by default."
        ),
    )
    configure_parser.add_argument(
        "--scope",
        choices=["local", "global"],
        default="local",
        help="Apply settings to local repo (.git/config) or global (~/.gitconfig)",
    )
    configure_parser.add_argument(
        "--preset",
        choices=["safe", "opinionated", "custom"],
        default="safe",
        help="Preset of settings to apply (safe is conservative)",
    )
    configure_parser.add_argument(
        "--enable",
        nargs="+",
        help=(
            "Features to enable for custom preset. Options: rerere zdiff3 patience "
            "rename-detect merge-backend rebase-autostash diff-color attributes drivers"
        ),
    )
    configure_parser.add_argument(
        "--disable",
        nargs="+",
        help="Features to disable for custom preset",
    )
    configure_parser.add_argument(
        "--lockfile-policy",
        choices=["ours", "theirs", "union", "none"],
        help="Policy for lockfiles in .gitattributes (default depends on preset)",
    )
    configure_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without applying",
    )
    configure_parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not prompt for confirmations",
    )
    configure_parser.add_argument(
        "--backup-path",
        help="Directory to store backups (default: .git-tidy/configure-repo.bak)",
    )
    configure_parser.add_argument(
        "--undo",
        action="store_true",
        help="Restore the last backup and exit",
    )
    configure_parser.set_defaults(func=cmd_configure_repo)

    # rebase-skip-merged subcommand
    rsm_parser = subparsers.add_parser(
        "rebase-skip-merged",
        help="Rebase current (or given) branch onto base, skipping commits already on base by content",
        description=(
            "Rebase while skipping commits whose content already exists on base (patch-id equivalence). "
            "Helps when an ancestor branch was rebased but landed unchanged on main."
        ),
    )
    rsm_parser.add_argument(
        "--base",
        help="Base commit/branch to rebase onto (default: origin/main)",
    )
    rsm_parser.add_argument(
        "--branch",
        help="Branch to rebase (default: current branch)",
    )
    # boolean paired options
    dry_group = rsm_parser.add_mutually_exclusive_group()
    dry_group.add_argument(
        "--dry-run", dest="dry_run", action="store_true", help="Show planned changes"
    )
    dry_group.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    rsm_parser.set_defaults(dry_run=False)

    prompt_group = rsm_parser.add_mutually_exclusive_group()
    prompt_group.add_argument(
        "--prompt",
        dest="prompt",
        action="store_true",
        help="Ask for confirmation before applying",
    )
    prompt_group.add_argument("--no-prompt", dest="prompt", action="store_false")
    rsm_parser.set_defaults(prompt=True)

    backup_group = rsm_parser.add_mutually_exclusive_group()
    backup_group.add_argument(
        "--backup",
        dest="backup",
        action="store_true",
        help="Create a backup branch before changes",
    )
    backup_group.add_argument("--no-backup", dest="backup", action="store_false")
    rsm_parser.set_defaults(backup=True)

    rsm_parser.add_argument(
        "--resume-from", help="Resume from this commit (SHA or index)"
    )
    rsm_parser.add_argument(
        "--chunk-size", type=int, help="Replay commits in chunks of N"
    )

    by_groups_group = rsm_parser.add_mutually_exclusive_group()
    by_groups_group.add_argument(
        "--by-groups",
        dest="by_groups",
        action="store_true",
        help="Replay commits grouped to reduce conflicts",
    )
    by_groups_group.add_argument(
        "--no-by-groups", dest="by_groups", action="store_false"
    )
    rsm_parser.set_defaults(by_groups=False)

    rsm_parser.add_argument(
        "--max-conflicts", type=int, help="Abort after N conflicts", default=None
    )

    opt_merge_group = rsm_parser.add_mutually_exclusive_group()
    opt_merge_group.add_argument(
        "--optimize-merge",
        dest="optimize_merge",
        action="store_true",
        help="Temporarily enable safer merge settings for this run",
    )
    opt_merge_group.add_argument(
        "--no-optimize-merge", dest="optimize_merge", action="store_false"
    )
    rsm_parser.set_defaults(optimize_merge=False)

    rsm_parser.add_argument(
        "--conflict-bias",
        choices=["ours", "theirs", "none"],
        default="none",
        help="Bias for conflicts (-X ours/theirs)",
    )

    rsm_parser.add_argument("--rerere-cache", help="Path to shared rerere cache")
    use_rerere_group = rsm_parser.add_mutually_exclusive_group()
    use_rerere_group.add_argument(
        "--use-rerere-cache",
        dest="use_rerere_cache",
        action="store_true",
        help="Import/export rerere cache for this run",
    )
    use_rerere_group.add_argument(
        "--no-use-rerere-cache", dest="use_rerere_cache", action="store_false"
    )
    rsm_parser.set_defaults(use_rerere_cache=False)

    auto_res_group = rsm_parser.add_mutually_exclusive_group()
    auto_res_group.add_argument(
        "--auto-resolve-trivial",
        dest="auto_resolve_trivial",
        action="store_true",
        help="Auto-continue trivial conflicts when possible",
    )
    auto_res_group.add_argument(
        "--no-auto-resolve-trivial", dest="auto_resolve_trivial", action="store_false"
    )
    rsm_parser.set_defaults(auto_resolve_trivial=False)

    rename_group = rsm_parser.add_mutually_exclusive_group()
    rename_group.add_argument(
        "--rename-detect",
        dest="rename_detect",
        action="store_true",
        help="Enable rename detection",
    )
    rename_group.add_argument(
        "--no-rename-detect", dest="rename_detect", action="store_false"
    )
    rsm_parser.set_defaults(rename_detect=True)

    lint_group = rsm_parser.add_mutually_exclusive_group()
    lint_group.add_argument(
        "--lint", dest="lint", action="store_true", help="Run lint after rebase"
    )
    lint_group.add_argument("--no-lint", dest="lint", action="store_false")
    rsm_parser.set_defaults(lint=False)

    test_group = rsm_parser.add_mutually_exclusive_group()
    test_group.add_argument(
        "--test", dest="test", action="store_true", help="Run tests after rebase"
    )
    test_group.add_argument("--no-test", dest="test", action="store_false")
    rsm_parser.set_defaults(test=False)

    build_group = rsm_parser.add_mutually_exclusive_group()
    build_group.add_argument(
        "--build", dest="build", action="store_true", help="Run build after rebase"
    )
    build_group.add_argument("--no-build", dest="build", action="store_false")
    rsm_parser.set_defaults(build=False)

    rsm_parser.add_argument(
        "--report",
        choices=["text", "json"],
        default="text",
        help="Output report format",
    )

    summary_group = rsm_parser.add_mutually_exclusive_group()
    summary_group.add_argument(
        "--summary", dest="summary", action="store_true", help="Print summary at end"
    )
    summary_group.add_argument("--no-summary", dest="summary", action="store_false")
    rsm_parser.set_defaults(summary=True)
    rsm_parser.set_defaults(func=cmd_rebase_skip_merged)

    # preflight-check
    pre_parser = subparsers.add_parser(
        "preflight-check",
        help="Verify clean worktree, fetch, and basic guards",
    )
    pre_parser.add_argument("--base")
    pre_parser.add_argument("--branch")
    allow_dirty = pre_parser.add_mutually_exclusive_group()
    allow_dirty.add_argument("--allow-dirty", dest="allow_dirty", action="store_true")
    allow_dirty.add_argument(
        "--no-allow-dirty", dest="allow_dirty", action="store_false"
    )
    pre_parser.set_defaults(allow_dirty=False)
    allow_wip = pre_parser.add_mutually_exclusive_group()
    allow_wip.add_argument("--allow-wip", dest="allow_wip", action="store_true")
    allow_wip.add_argument("--no-allow-wip", dest="allow_wip", action="store_false")
    pre_parser.set_defaults(allow_wip=False)
    dry_group = pre_parser.add_mutually_exclusive_group()
    dry_group.add_argument("--dry-run", dest="dry_run", action="store_true")
    dry_group.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    pre_parser.set_defaults(dry_run=False)
    pre_parser.set_defaults(func=cmd_preflight_check)

    # select-base
    sel_parser = subparsers.add_parser(
        "select-base",
        help="Select a sensible rebase base (merge-base or fallback)",
    )
    sel_parser.add_argument(
        "--preferred",
        nargs="+",
        default=["origin/main", "main", "origin/master", "master"],
    )
    sel_parser.add_argument("--fallback", default="HEAD~10")
    sel_parser.set_defaults(func=cmd_select_base)

    # auto-continue
    ac_parser = subparsers.add_parser(
        "auto-continue",
        help="Continue cherry-pick/rebase if possible",
    )
    ac_parser.set_defaults(func=cmd_auto_continue)

    # auto-resolve-trivial
    art_parser = subparsers.add_parser(
        "auto-resolve-trivial",
        help="Attempt trivial auto-resolutions and continue",
    )
    art_parser.set_defaults(func=cmd_auto_resolve_trivial)

    # chunked-replay
    cr_parser = subparsers.add_parser(
        "chunked-replay",
        help="Replay given commits in chunks on top of a base",
    )
    cr_parser.add_argument("--base", required=True)
    cr_parser.add_argument("--commits", help="Comma-separated SHAs")
    cr_parser.add_argument("--chunk-size", type=int, required=True)
    cr_parser.set_defaults(func=cmd_chunked_replay)

    # range-diff-report
    rdiff_parser = subparsers.add_parser(
        "range-diff-report",
        help="Print git range-diff between two ranges",
    )
    rdiff_parser.add_argument("old", help="Old range (e.g., origin/main...branch)")
    rdiff_parser.add_argument("new", help="New range")
    rdiff_parser.set_defaults(func=cmd_range_diff_report)

    # validate
    val_parser = subparsers.add_parser(
        "validate",
        help="Run lint/tests/build and report",
    )
    lint_group = val_parser.add_mutually_exclusive_group()
    lint_group.add_argument("--lint", dest="lint", action="store_true")
    lint_group.add_argument("--no-lint", dest="lint", action="store_false")
    val_parser.set_defaults(lint=False)
    test_group = val_parser.add_mutually_exclusive_group()
    test_group.add_argument("--test", dest="test", action="store_true")
    test_group.add_argument("--no-test", dest="test", action="store_false")
    val_parser.set_defaults(test=False)
    build_group = val_parser.add_mutually_exclusive_group()
    build_group.add_argument("--build", dest="build", action="store_true")
    build_group.add_argument("--no-build", dest="build", action="store_false")
    val_parser.set_defaults(build=False)
    val_parser.set_defaults(func=cmd_validate)

    # rerere-share
    rr_parser = subparsers.add_parser(
        "rerere-share",
        help="Import or export a rerere cache",
    )
    rr_parser.add_argument("--action", choices=["import", "export"], required=True)
    rr_parser.add_argument("--path", required=True)
    rr_parser.set_defaults(func=cmd_rerere_share)

    # checkpoints
    cpc_parser = subparsers.add_parser(
        "checkpoint-create",
        help="Create a git-tidy backup checkpoint",
    )
    cpc_parser.set_defaults(func=cmd_checkpoint_create)
    cpr_parser = subparsers.add_parser(
        "checkpoint-restore",
        help="Restore from last git-tidy backup",
    )
    cpr_parser.set_defaults(func=cmd_checkpoint_restore)

    # smart-rebase
    sr_parser = subparsers.add_parser(
        "smart-rebase",
        help="Perform an orchestrated rebase with safety, dedup and validation",
        description=(
            "Preflight checks, choose base, rebase while skipping merged content, optionally in chunks, "
            "with temporary merge optimizations and post-run validation/reporting."
        ),
    )
    sr_parser.add_argument("--branch")
    sr_parser.add_argument("--base")
    # paired booleans
    dry_group = sr_parser.add_mutually_exclusive_group()
    dry_group.add_argument("--dry-run", dest="dry_run", action="store_true")
    dry_group.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    sr_parser.set_defaults(dry_run=False)

    prompt_group = sr_parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", dest="prompt", action="store_true")
    prompt_group.add_argument("--no-prompt", dest="prompt", action="store_false")
    sr_parser.set_defaults(prompt=True)

    backup_group = sr_parser.add_mutually_exclusive_group()
    backup_group.add_argument("--backup", dest="backup", action="store_true")
    backup_group.add_argument("--no-backup", dest="backup", action="store_false")
    sr_parser.set_defaults(backup=True)

    opt_merge_group = sr_parser.add_mutually_exclusive_group()
    opt_merge_group.add_argument(
        "--optimize-merge", dest="optimize_merge", action="store_true"
    )
    opt_merge_group.add_argument(
        "--no-optimize-merge", dest="optimize_merge", action="store_false"
    )
    sr_parser.set_defaults(optimize_merge=False)

    sr_parser.add_argument(
        "--conflict-bias", choices=["ours", "theirs", "none"], default="none"
    )
    sr_parser.add_argument("--chunk-size", type=int)

    triv_group = sr_parser.add_mutually_exclusive_group()
    triv_group.add_argument(
        "--auto-resolve-trivial", dest="auto_resolve_trivial", action="store_true"
    )
    triv_group.add_argument(
        "--no-auto-resolve-trivial", dest="auto_resolve_trivial", action="store_false"
    )
    sr_parser.set_defaults(auto_resolve_trivial=False)

    sr_parser.add_argument("--max-conflicts", type=int)

    rename_group = sr_parser.add_mutually_exclusive_group()
    rename_group.add_argument(
        "--rename-detect", dest="rename_detect", action="store_true"
    )
    rename_group.add_argument(
        "--no-rename-detect", dest="rename_detect", action="store_false"
    )
    sr_parser.set_defaults(rename_detect=True)

    lint_group = sr_parser.add_mutually_exclusive_group()
    lint_group.add_argument("--lint", dest="lint", action="store_true")
    lint_group.add_argument("--no-lint", dest="lint", action="store_false")
    sr_parser.set_defaults(lint=False)

    test_group = sr_parser.add_mutually_exclusive_group()
    test_group.add_argument("--test", dest="test", action="store_true")
    test_group.add_argument("--no-test", dest="test", action="store_false")
    sr_parser.set_defaults(test=False)

    build_group = sr_parser.add_mutually_exclusive_group()
    build_group.add_argument("--build", dest="build", action="store_true")
    build_group.add_argument("--no-build", dest="build", action="store_false")
    sr_parser.set_defaults(build=False)

    sr_parser.add_argument("--report", choices=["text", "json"], default="text")

    summary_group = sr_parser.add_mutually_exclusive_group()
    summary_group.add_argument("--summary", dest="summary", action="store_true")
    summary_group.add_argument("--no-summary", dest="summary", action="store_false")
    sr_parser.set_defaults(summary=True)

    skipm_group = sr_parser.add_mutually_exclusive_group()
    skipm_group.add_argument("--skip-merged", dest="skip_merged", action="store_true")
    skipm_group.add_argument(
        "--no-skip-merged", dest="skip_merged", action="store_false"
    )
    sr_parser.set_defaults(skip_merged=True)

    sr_parser.set_defaults(func=cmd_smart_rebase)

    # smart-merge
    sm_parser = subparsers.add_parser(
        "smart-merge",
        help="Preview or perform a merge with ort + rename detection and safety",
        description=(
            "Safely merge a branch into a target with ort and find-renames, previewing or applying "
            "with temporary safer merge settings and validation."
        ),
    )
    sm_parser.add_argument("--branch", required=True, help="Source branch to merge")
    sm_parser.add_argument("--into", help="Target branch (default: current branch)")

    apply_group = sm_parser.add_mutually_exclusive_group()
    apply_group.add_argument(
        "--apply",
        dest="apply",
        action="store_true",
        help="Apply the merge; otherwise preview only",
    )
    apply_group.add_argument("--no-apply", dest="apply", action="store_false")
    sm_parser.set_defaults(apply=False)

    prompt_group = sm_parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", dest="prompt", action="store_true")
    prompt_group.add_argument("--no-prompt", dest="prompt", action="store_false")
    sm_parser.set_defaults(prompt=True)

    backup_group = sm_parser.add_mutually_exclusive_group()
    backup_group.add_argument("--backup", dest="backup", action="store_true")
    backup_group.add_argument("--no-backup", dest="backup", action="store_false")
    sm_parser.set_defaults(backup=True)

    opt_merge_group = sm_parser.add_mutually_exclusive_group()
    opt_merge_group.add_argument(
        "--optimize-merge", dest="optimize_merge", action="store_true"
    )
    opt_merge_group.add_argument(
        "--no-optimize-merge", dest="optimize_merge", action="store_false"
    )
    sm_parser.set_defaults(optimize_merge=False)

    sm_parser.add_argument(
        "--conflict-bias", choices=["ours", "theirs", "none"], default="none"
    )

    rename_group = sm_parser.add_mutually_exclusive_group()
    rename_group.add_argument(
        "--rename-detect", dest="rename_detect", action="store_true"
    )
    rename_group.add_argument(
        "--no-rename-detect", dest="rename_detect", action="store_false"
    )
    sm_parser.set_defaults(rename_detect=True)
    sm_parser.add_argument(
        "--rename-threshold", type=int, help="find-renames threshold percent (0-100)"
    )

    triv_group = sm_parser.add_mutually_exclusive_group()
    triv_group.add_argument(
        "--auto-resolve-trivial", dest="auto_resolve_trivial", action="store_true"
    )
    triv_group.add_argument(
        "--no-auto-resolve-trivial", dest="auto_resolve_trivial", action="store_false"
    )
    sm_parser.set_defaults(auto_resolve_trivial=False)

    sm_parser.add_argument("--max-conflicts", type=int)

    lint_group = sm_parser.add_mutually_exclusive_group()
    lint_group.add_argument("--lint", dest="lint", action="store_true")
    lint_group.add_argument("--no-lint", dest="lint", action="store_false")
    sm_parser.set_defaults(lint=False)

    test_group = sm_parser.add_mutually_exclusive_group()
    test_group.add_argument("--test", dest="test", action="store_true")
    test_group.add_argument("--no-test", dest="test", action="store_false")
    sm_parser.set_defaults(test=False)

    build_group = sm_parser.add_mutually_exclusive_group()
    build_group.add_argument("--build", dest="build", action="store_true")
    build_group.add_argument("--no-build", dest="build", action="store_false")
    sm_parser.set_defaults(build=False)

    sm_parser.add_argument("--report", choices=["text", "json"], default="text")

    sm_parser.set_defaults(func=cmd_smart_merge)

    # smart-revert
    svr_parser = subparsers.add_parser(
        "smart-revert",
        help="Preview or perform revert(s) with strategy hints and safety",
        description=(
            "Safely revert commit(s) or a range with strategy bias and rename detection. "
            "Defaults to preview; use --apply to perform changes."
        ),
    )
    svr_parser.add_argument(
        "--commits",
        action="append",
        help="Commit SHAs to revert (comma-separated or repeated)",
    )
    svr_parser.add_argument("--range", help="Commit range A..B to revert (inclusive)")
    svr_parser.add_argument("--count", type=int, help="Revert last N commits")

    apply_group = svr_parser.add_mutually_exclusive_group()
    apply_group.add_argument("--apply", dest="apply", action="store_true")
    apply_group.add_argument("--no-apply", dest="apply", action="store_false")
    svr_parser.set_defaults(apply=False)

    prompt_group = svr_parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", dest="prompt", action="store_true")
    prompt_group.add_argument("--no-prompt", dest="prompt", action="store_false")
    svr_parser.set_defaults(prompt=True)

    backup_group = svr_parser.add_mutually_exclusive_group()
    backup_group.add_argument("--backup", dest="backup", action="store_true")
    backup_group.add_argument("--no-backup", dest="backup", action="store_false")
    svr_parser.set_defaults(backup=True)

    opt_merge_group = svr_parser.add_mutually_exclusive_group()
    opt_merge_group.add_argument(
        "--optimize-merge", dest="optimize_merge", action="store_true"
    )
    opt_merge_group.add_argument(
        "--no-optimize-merge", dest="optimize_merge", action="store_false"
    )
    svr_parser.set_defaults(optimize_merge=False)

    svr_parser.add_argument(
        "--conflict-bias", choices=["ours", "theirs", "none"], default="none"
    )

    rename_group = svr_parser.add_mutually_exclusive_group()
    rename_group.add_argument(
        "--rename-detect", dest="rename_detect", action="store_true"
    )
    rename_group.add_argument(
        "--no-rename-detect", dest="rename_detect", action="store_false"
    )
    svr_parser.set_defaults(rename_detect=True)
    svr_parser.add_argument("--rename-threshold", type=int)

    triv_group = svr_parser.add_mutually_exclusive_group()
    triv_group.add_argument(
        "--auto-resolve-trivial", dest="auto_resolve_trivial", action="store_true"
    )
    triv_group.add_argument(
        "--no-auto-resolve-trivial", dest="auto_resolve_trivial", action="store_false"
    )
    svr_parser.set_defaults(auto_resolve_trivial=False)

    svr_parser.add_argument("--max-conflicts", type=int)

    lint_group = svr_parser.add_mutually_exclusive_group()
    lint_group.add_argument("--lint", dest="lint", action="store_true")
    lint_group.add_argument("--no-lint", dest="lint", action="store_false")
    svr_parser.set_defaults(lint=False)

    test_group = svr_parser.add_mutually_exclusive_group()
    test_group.add_argument("--test", dest="test", action="store_true")
    test_group.add_argument("--no-test", dest="test", action="store_false")
    svr_parser.set_defaults(test=False)

    build_group = svr_parser.add_mutually_exclusive_group()
    build_group.add_argument("--build", dest="build", action="store_true")
    build_group.add_argument("--no-build", dest="build", action="store_false")
    svr_parser.set_defaults(build=False)

    svr_parser.add_argument("--report", choices=["text", "json"], default="text")
    svr_parser.set_defaults(func=cmd_smart_revert)

    # select-reverts helper
    selr_parser = subparsers.add_parser(
        "select-reverts",
        help="Select commits to revert via filters; prints SHAs",
    )
    selr_parser.add_argument("--range", help="Range A..B (e.g., main..HEAD)")
    selr_parser.add_argument("--count", type=int, help="Last N commits")
    selr_parser.add_argument("--grep", help="Filter commit messages (regex)")
    selr_parser.add_argument("--author", help="Filter by author")
    selr_parser.set_defaults(func=cmd_select_reverts)

    return parser


def main() -> None:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # If no subcommand is provided, show help
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Execute the subcommand
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
