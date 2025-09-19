"""Git history tidy up script core functionality.

E.g. reorders commits to group those with similar file changes while preserving relative order within each group.
"""

import os
import subprocess
import sys
import tempfile
from typing import Optional, TypedDict, Any


class CommitInfo(TypedDict):
    sha: str
    subject: str
    files: set[str]


class GitTidy:
    def __init__(self) -> None:
        self.original_branch: Optional[str] = None
        self.original_head: Optional[str] = None
        self.backup_branch: Optional[str] = None

    def run_git(
        self,
        cmd: list[str],
        check_output: bool = True,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run git command with error handling."""
        try:
            result = subprocess.run(
                ["git"] + cmd,
                capture_output=True,
                text=True,
                check=check_output,
                env=env,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise GitError(
                f"Git command failed: {' '.join(cmd)}\nError: {e.stderr}"
            ) from e

    def create_backup(self) -> None:
        """Create a backup branch at current HEAD."""
        self.original_branch = self.run_git(["branch", "--show-current"]).stdout.strip()
        self.original_head = self.run_git(["rev-parse", "HEAD"]).stdout.strip()
        self.backup_branch = f"backup-{self.original_head[:8]}"

        self.run_git(["branch", self.backup_branch, "HEAD"])
        print(f"Created backup branch: {self.backup_branch}")

    def restore_from_backup(self) -> None:
        """Restore to original state if something goes wrong."""
        if self.backup_branch and self.original_head:
            print("Restoring from backup due to error...")

            # Check if we're in the middle of a rebase and abort it first
            try:
                status_result = self.run_git(
                    ["status", "--porcelain=v1"], check_output=False
                )
                if status_result.returncode == 0:
                    # Check if rebase is in progress
                    rebase_head_path = ".git/REBASE_HEAD"
                    if os.path.exists(rebase_head_path):
                        print("Aborting incomplete rebase...")
                        self.run_git(["rebase", "--abort"], check_output=False)
            except GitError:
                # If status check fails, continue with reset anyway
                pass

            self.run_git(["reset", "--hard", self.original_head])
            self.run_git(["branch", "-D", self.backup_branch], check_output=False)

    def cleanup_backup(self) -> None:
        """Clean up backup branch after successful operation."""
        if self.backup_branch:
            self.run_git(["branch", "-D", self.backup_branch], check_output=False)
            print(f"Cleaned up backup branch: {self.backup_branch}")

    def get_commits_to_rebase(self, base_ref: Optional[str] = None) -> list[CommitInfo]:
        """Get list of commits to reorder."""
        if base_ref is None:
            # Find merge base with main/master
            try:
                base_ref = self.run_git(["merge-base", "HEAD", "main"]).stdout.strip()
            except GitError:
                try:
                    base_ref = self.run_git(
                        ["merge-base", "HEAD", "master"]
                    ).stdout.strip()
                except GitError:
                    # Fallback to last 10 commits
                    base_ref = "HEAD~10"

        # Get commit range
        commit_range = f"{base_ref}..HEAD"
        result = self.run_git(
            ["log", commit_range, "--pretty=format:%H|%s", "--reverse"]  # Oldest first
        )

        commits: list[CommitInfo] = []
        for line in result.stdout.strip().split("\n"):
            if line:
                sha, subject = line.split("|", 1)
                commit_info: CommitInfo = {
                    "sha": sha,
                    "subject": subject,
                    "files": self.get_commit_files(sha),
                }
                commits.append(commit_info)

        return commits

    def get_commit_files(self, sha: str) -> set[str]:
        """Get set of files changed in a commit."""
        result = self.run_git(["show", "--name-only", "--pretty=format:", sha])
        files = {
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        }
        return files

    def get_commit_message(self, sha: str) -> str:
        """Get the full commit message for a commit."""
        result = self.run_git(["show", "--pretty=format:%B", "--no-patch", sha])
        return result.stdout.strip()

    def calculate_similarity(self, files1: set[str], files2: set[str]) -> float:
        """Calculate Jaccard similarity between two sets of files."""
        if not files1 and not files2:
            return 1.0
        if not files1 or not files2:
            return 0.0

        intersection = len(files1.intersection(files2))
        union = len(files1.union(files2))
        return intersection / union if union > 0 else 0.0

    def group_commits(
        self, commits: list[CommitInfo], similarity_threshold: float = 0.3
    ) -> list[list[CommitInfo]]:
        """Group commits based on file similarity using a greedy approach."""
        if not commits:
            return []

        groups = []
        used = set()

        for i, commit in enumerate(commits):
            if i in used:
                continue

            # Start new group with this commit
            current_group = [commit]
            used.add(i)

            # Find similar commits that come later
            for j in range(i + 1, len(commits)):
                if j in used:
                    continue

                # Check similarity with any commit in current group
                max_similarity = max(
                    self.calculate_similarity(commit["files"], commits[j]["files"])
                    for commit in current_group
                )

                if max_similarity >= similarity_threshold:
                    current_group.append(commits[j])
                    used.add(j)

            groups.append(current_group)

        return groups

    def create_rebase_todo(self, groups: list[list[CommitInfo]]) -> str:
        """Create interactive rebase todo list."""
        todo_lines = []

        for group_idx, group in enumerate(groups):
            if group_idx > 0:
                todo_lines.append(
                    f"# Group {group_idx + 1}: {self.describe_group(group)}"
                )

            for _commit_idx, commit in enumerate(group):
                action = "pick"
                todo_lines.append(f"{action} {commit['sha'][:8]} {commit['subject']}")

        return "\n".join(todo_lines)

    def describe_group(self, group: list[CommitInfo]) -> str:
        """Create a description for a group of commits."""
        all_files = set()
        for commit in group:
            all_files.update(commit["files"])

        if len(all_files) <= 3:
            return f"Files: {', '.join(sorted(all_files))}"
        else:
            sample_files = sorted(all_files)[:3]
            return f"Files: {', '.join(sample_files)} and {len(all_files) - 3} more"

    def perform_rebase(self, groups: list[list[CommitInfo]]) -> bool:
        """Perform the actual rebase operation."""
        if len(groups) <= 1:
            print("No grouping needed - commits are already optimally ordered")
            return True

        # Create todo file
        todo_content = self.create_rebase_todo(groups)

        # Get base commit
        first_commit_sha = groups[0][0]["sha"]
        base_commit = self.run_git(["rev-parse", f"{first_commit_sha}^"]).stdout.strip()

        print(
            f"Rebasing {sum(len(g) for g in groups)} commits into {len(groups)} groups..."
        )
        print("\nProposed grouping:")
        for i, group in enumerate(groups):
            print(
                f"  Group {i + 1}: {len(group)} commits - {self.describe_group(group)}"
            )

        # Confirm with user
        response = input("\nProceed with rebase? (y/N): ")
        if response.lower() != "y":
            print("Rebase cancelled")
            return False

        # Write todo to temporary file and start interactive rebase
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(todo_content)
            todo_file = f.name

        try:
            # Set up environment for non-interactive rebase
            env = os.environ.copy()
            env["GIT_SEQUENCE_EDITOR"] = f"cp {todo_file}"

            result = self.run_git(
                ["rebase", "-i", base_commit], check_output=False, env=env
            )

            if result.returncode != 0:
                print(f"Rebase failed: {result.stderr}")
                return False

            print("Rebase completed successfully!")
            return True

        finally:
            os.unlink(todo_file)

    def perform_split_rebase(self, commits: list[CommitInfo]) -> bool:
        """Perform the actual split rebase operation."""
        # Check if any commits need splitting
        needs_splitting = any(len(commit["files"]) > 1 for commit in commits)
        if not needs_splitting:
            print("No commits need splitting - all commits already have single files")
            return True

        # Get base commit
        first_commit_sha = commits[0]["sha"]
        base_commit = self.run_git(["rev-parse", f"{first_commit_sha}^"]).stdout.strip()

        total_files = sum(len(commit["files"]) for commit in commits)
        print(
            f"Splitting {len(commits)} commits into {total_files} file-based commits..."
        )
        print("\nProposed splitting:")
        for commit in commits:
            if len(commit["files"]) > 1:
                print(
                    f"  Commit {commit['sha'][:8]}: {len(commit['files'])} files -> {len(commit['files'])} commits"
                )
                for file in sorted(commit["files"]):
                    print(f"    - split off {file}")
            else:
                print(
                    f"  Commit {commit['sha'][:8]}: {len(commit['files'])} file -> keep as-is"
                )

        # Confirm with user
        response = input("\nProceed with split rebase? (y/N): ")
        if response.lower() != "y":
            print("Split rebase cancelled")
            return False

        # Reset to base commit
        print(f"Resetting to base commit {base_commit[:8]}...")
        self.run_git(["reset", "--soft", base_commit])

        # Create new commits for each file
        new_commits = []
        for commit in commits:
            files = sorted(commit["files"])
            original_message = self.get_commit_message(commit["sha"])

            if len(files) <= 1:
                # Single file or no files - create commit as-is
                if files:
                    # Cherry-pick the commit to get the changes
                    self.run_git(["cherry-pick", "--no-commit", commit["sha"]])
                    # Reset and add only the specific file
                    self.run_git(["reset", "HEAD"])
                    self.run_git(["add", files[0]])
                    self.run_git(["commit", "-m", original_message])
                    new_commits.append(original_message)
                else:
                    # Empty commit - just commit with message
                    self.run_git(["commit", "--allow-empty", "-m", original_message])
                    new_commits.append(original_message)
            else:
                # Multiple files - create separate commits for each file
                for file in files:
                    # Cherry-pick the commit to get the changes
                    self.run_git(["cherry-pick", "--no-commit", commit["sha"]])
                    # Reset and add only the specific file
                    self.run_git(["reset", "HEAD"])
                    self.run_git(["add", file])
                    # Create commit with split message
                    split_message = f"split off {file}\n\n{original_message}"
                    self.run_git(["commit", "-m", split_message])
                    new_commits.append(split_message)

        print(f"Successfully created {len(new_commits)} commits:")
        for i, message in enumerate(new_commits, 1):
            first_line = message.split("\n")[0]
            print(f"  {i}. {first_line}")

        return True

    def split_commits(self, base_ref: Optional[str] = None) -> None:
        """Split commits into separate commits, one per file."""
        try:
            # Create backup
            self.create_backup()

            # Get commits to split
            commits = self.get_commits_to_rebase(base_ref)
            if not commits:
                print("No commits found to split")
                self.cleanup_backup()
                return

            print(f"Found {len(commits)} commits to split")

            # Perform split rebase
            success = self.perform_split_rebase(commits)

            if success:
                self.cleanup_backup()
            else:
                self.restore_from_backup()

        except Exception as e:
            print(f"Error: {e}")
            self.restore_from_backup()
            sys.exit(1)


    def configure_repo(self, options: dict[str, Any]) -> None:
        """Configure repository/global git settings to reduce merge pain.

        Currently implements the 'safe' preset:
        - Enable rerere with autoUpdate
        - Use zdiff3 conflict style for clearer conflicts
        - Use patience diff with indent heuristic
        - Enable rename detection and raise rename limits
        - Use merge backend for rebase and autostash
        - Improve diff coloring for moved lines

        Options:
            scope: 'local' or 'global' (default: 'local')
            preset: 'safe'|'opinionated'|'custom' (currently only 'safe' applied)
            dry_run: bool (default: False)
        """
        scope = options.get("scope", "local")
        preset = options.get("preset", "safe")
        dry_run = bool(options.get("dry_run", False))

        if scope not in {"local", "global"}:
            scope = "local"

        # Only implement 'safe' preset for now; other presets are ignored gracefully
        settings: list[tuple[str, str]] = [
            ("rerere.enabled", "true"),
            ("rerere.autoUpdate", "true"),
            ("merge.conflictStyle", "zdiff3"),
            ("diff.algorithm", "patience"),
            ("diff.indentHeuristic", "true"),
            ("diff.renames", "true"),
            ("merge.renames", "true"),
            ("merge.renameLimit", "32767"),
            ("rebase.backend", "merge"),
            ("rebase.autoStash", "true"),
            ("diff.colorMoved", "zebra"),
            ("color.ui", "auto"),
        ]

        scope_flag = "--global" if scope == "global" else "--local"

        if dry_run:
            print("Planned git configuration changes:")
            for key, value in settings:
                print(f"  git config {scope_flag} {key} {value}")
            return

        for key, value in settings:
            self.run_git(["config", scope_flag, key, value])

    def run(
        self, base_ref: Optional[str] = None, similarity_threshold: float = 0.3
    ) -> None:
        """Main execution function."""
        try:
            # Create backup
            self.create_backup()

            # Get commits to rebase
            commits = self.get_commits_to_rebase(base_ref)
            if not commits:
                print("No commits found to rebase")
                self.cleanup_backup()
                return

            print(f"Found {len(commits)} commits to analyze")

            # Group commits
            groups = self.group_commits(commits, similarity_threshold)

            # Perform rebase
            success = self.perform_rebase(groups)

            if success:
                self.cleanup_backup()
            else:
                self.restore_from_backup()

        except Exception as e:
            print(f"Error: {e}")
            self.restore_from_backup()
            sys.exit(1)


class GitError(Exception):
    """Custom exception for git-related errors."""

    pass
