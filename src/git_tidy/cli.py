"""Command-line interface for git-tidy."""

import argparse
import sys

from .core import GitTidy


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Tidy up git commits. Currently groups git commits by file similarity.'
    )
    parser.add_argument('--base', help='Base commit/branch for rebase range')
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.3,
        help='Similarity threshold (0.0-1.0, default: 0.3)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show grouping without performing rebase'
    )

    args = parser.parse_args()

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


if __name__ == '__main__':
    main()