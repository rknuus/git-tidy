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
        git_tidy.run(args.base, args.threshold)


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
        git_tidy.split_commits(args.base)


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

    git_tidy.rebase_skip_merged(base_ref=args.base, branch=args.branch, dry_run=bool(args.dry_run))


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
    rsm_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which commits would be replayed without changing anything",
    )
    rsm_parser.set_defaults(func=cmd_rebase_skip_merged)

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
