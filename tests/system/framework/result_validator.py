"""Result validation framework for git-tidy system tests."""

import hashlib
import subprocess
from pathlib import Path

import pygit2

from .git_tidy_runner import ExpectedOutcome, GitTidyResult


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


class RepositoryState:
    """Captures the state of a git repository for comparison."""

    def __init__(self, repo_path: Path):
        """Capture the current repository state."""
        self.repo_path = repo_path
        self.repo = pygit2.Repository(str(repo_path))

        # Capture basic repository info
        self.is_empty = self.repo.is_empty
        self.head_sha = None if self.is_empty else str(self.repo.head.target)
        self.commit_count = (
            0 if self.is_empty else len(list(self.repo.walk(self.repo.head.target)))
        )

        # Capture branches
        self.branches = set(self.repo.branches.local)

        # Capture tags
        self.tags = {
            ref.split("/")[-1]
            for ref in self.repo.references
            if ref.startswith("refs/tags/")
        }

        # Capture file checksums
        self.file_checksums = self._compute_file_checksums()

        # Capture commit history
        self.commit_history = self._get_commit_history()

    def _compute_file_checksums(self) -> dict[str, str]:
        """Compute checksums for all files in the working directory."""
        checksums = {}
        if self.repo_path.exists():
            for file_path in self.repo_path.rglob("*"):
                if file_path.is_file() and ".git" not in file_path.parts:
                    try:
                        content = file_path.read_bytes()
                        checksums[str(file_path.relative_to(self.repo_path))] = (
                            hashlib.sha256(content).hexdigest()
                        )
                    except Exception:
                        # Skip files that can't be read
                        pass
        return checksums

    def _get_commit_history(self) -> list[dict[str, str]]:
        """Get simplified commit history for comparison."""
        if self.is_empty:
            return []

        history = []
        for commit in self.repo.walk(self.repo.head.target):
            history.append(
                {
                    "sha": str(commit.id),
                    "message": commit.message.strip(),
                    "author": commit.author.name,
                }
            )
        return history


class ResultValidator:
    """Validates git-tidy command results against expectations."""

    def __init__(self):
        """Initialize the validator."""
        pass

    def validate_result(
        self,
        result: GitTidyResult,
        expected_outcome: ExpectedOutcome,
        pre_state: RepositoryState,
        post_state: RepositoryState,
    ) -> None:
        """Validate a git-tidy result against expected outcome."""
        if expected_outcome == ExpectedOutcome.SUCCESS_WITH_CHANGES:
            self._validate_success_with_changes(result, pre_state, post_state)
        elif expected_outcome == ExpectedOutcome.SUCCESS_NO_CHANGES:
            self._validate_success_no_changes(result, pre_state, post_state)
        elif expected_outcome == ExpectedOutcome.PREVIEW_ONLY:
            self._validate_preview_only(result, pre_state, post_state)
        elif expected_outcome == ExpectedOutcome.CONFLICT_REPORTED:
            self._validate_conflict_reported(result, pre_state, post_state)
        elif expected_outcome == ExpectedOutcome.ERROR_GRACEFUL:
            self._validate_error_graceful(result, pre_state, post_state)
        else:
            raise ValidationError(f"Unknown expected outcome: {expected_outcome}")

        # Always validate repository integrity
        self._validate_repository_integrity(post_state)

    def _validate_success_with_changes(
        self,
        result: GitTidyResult,
        pre_state: RepositoryState,
        post_state: RepositoryState,
    ) -> None:
        """Validate successful execution with repository changes."""
        if result.exit_code != 0:
            raise ValidationError(
                f"Expected success but got exit code {result.exit_code}: {result.stderr}"
            )

        # Check that repository state changed
        if (
            pre_state.head_sha == post_state.head_sha
            and pre_state.commit_count == post_state.commit_count
        ):
            raise ValidationError(
                "Expected changes but repository state appears unchanged"
            )

        # Validate file content preservation (checksums should be same)
        self._validate_content_preservation(pre_state, post_state)

    def _validate_success_no_changes(
        self,
        result: GitTidyResult,
        pre_state: RepositoryState,
        post_state: RepositoryState,
    ) -> None:
        """Validate successful execution with no repository changes."""
        if result.exit_code != 0:
            raise ValidationError(
                f"Expected success but got exit code {result.exit_code}: {result.stderr}"
            )

        # Check that repository state is unchanged
        if pre_state.head_sha != post_state.head_sha:
            raise ValidationError("Expected no changes but HEAD SHA changed")

        if pre_state.commit_count != post_state.commit_count:
            raise ValidationError("Expected no changes but commit count changed")

    def _validate_preview_only(
        self,
        result: GitTidyResult,
        pre_state: RepositoryState,
        post_state: RepositoryState,
    ) -> None:
        """Validate preview-only execution (no repository changes)."""
        if result.exit_code != 0:
            raise ValidationError(
                f"Expected success but got exit code {result.exit_code}: {result.stderr}"
            )

        # Repository should be completely unchanged
        if pre_state.head_sha != post_state.head_sha:
            raise ValidationError("Preview mode should not change repository")

        if pre_state.commit_history != post_state.commit_history:
            raise ValidationError("Preview mode should not change commit history")

    def _validate_conflict_reported(
        self,
        result: GitTidyResult,
        pre_state: RepositoryState,
        post_state: RepositoryState,
    ) -> None:
        """Validate that conflicts were properly reported."""
        # Conflicts might result in non-zero exit code or zero with conflict reporting
        conflict_indicators = [
            "conflict",
            "merge conflict",
            "unable to merge",
            "conflicting changes",
        ]

        output_text = (result.stdout + result.stderr).lower()
        if not any(indicator in output_text for indicator in conflict_indicators):
            raise ValidationError(
                "Expected conflict reporting but none found in output"
            )

    def _validate_error_graceful(
        self,
        result: GitTidyResult,
        pre_state: RepositoryState,
        post_state: RepositoryState,
    ) -> None:
        """Validate graceful error handling."""
        if result.exit_code == 0:
            raise ValidationError("Expected error but command succeeded")

        # Repository should be unchanged after error
        if pre_state.head_sha != post_state.head_sha:
            raise ValidationError("Repository should be unchanged after error")

        # Error message should be informative
        if not result.stderr and not result.stdout:
            raise ValidationError("Expected error message but got no output")

    def _validate_repository_integrity(self, post_state: RepositoryState) -> None:
        """Validate that the repository is in a valid state."""
        try:
            # Run git fsck to check repository integrity
            result = subprocess.run(
                ["git", "fsck", "--full"],
                cwd=post_state.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0 and "error:" in result.stderr.lower():
                raise ValidationError(
                    f"Repository integrity check failed: {result.stderr}"
                )

        except Exception as e:
            raise ValidationError(
                f"Failed to run repository integrity check: {e}"
            ) from e

    def _validate_content_preservation(
        self, pre_state: RepositoryState, post_state: RepositoryState
    ) -> None:
        """Validate that file contents are preserved."""
        # Get the set of files that should be preserved
        preserved_files = set(pre_state.file_checksums.keys()) & set(
            post_state.file_checksums.keys()
        )

        for file_path in preserved_files:
            pre_checksum = pre_state.file_checksums[file_path]
            post_checksum = post_state.file_checksums[file_path]

            if pre_checksum != post_checksum:
                raise ValidationError(f"File content changed unexpectedly: {file_path}")

    def validate_backup_created(self, repo_path: Path, expected: bool = True) -> None:
        """Validate that backup branch was created when expected."""
        repo = pygit2.Repository(str(repo_path))
        backup_branches = [
            branch for branch in repo.branches.local if branch.startswith("backup-")
        ]

        if expected and not backup_branches:
            raise ValidationError("Expected backup branch to be created but none found")
        elif not expected and backup_branches:
            raise ValidationError(
                f"Unexpected backup branch created: {backup_branches}"
            )

    def validate_commit_count_change(
        self,
        pre_state: RepositoryState,
        post_state: RepositoryState,
        expected_change: int,
    ) -> None:
        """Validate that commit count changed by expected amount."""
        actual_change = post_state.commit_count - pre_state.commit_count

        if actual_change != expected_change:
            raise ValidationError(
                f"Expected commit count change of {expected_change}, "
                f"but got {actual_change} "
                f"(from {pre_state.commit_count} to {post_state.commit_count})"
            )
