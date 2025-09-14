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
