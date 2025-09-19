"""Git-tidy command execution wrapper for system tests."""

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ExpectedOutcome(Enum):
    """Expected outcomes for git-tidy commands."""

    SUCCESS_WITH_CHANGES = "success_changes"  # Command succeeds, repo modified
    SUCCESS_NO_CHANGES = "success_no_changes"  # Command succeeds, no changes needed
    PREVIEW_ONLY = "preview"  # Dry-run shows what would happen
    CONFLICT_REPORTED = "conflict"  # Conflicts detected and reported
    ERROR_GRACEFUL = "error_graceful"  # Command fails gracefully


@dataclass
class GitTidyResult:
    """Result of a git-tidy command execution."""

    command: str
    args: list[str]
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    repo_path: Path


@dataclass
class TestSpec:
    """Specification for a system test."""

    command: str
    args: list[str]
    repository_type: str
    expected_outcome: ExpectedOutcome
    description: str


class GitTidyRunner:
    """Execute git-tidy commands and capture results."""

    def __init__(self, timeout: int = 30):
        """Initialize the runner with optional timeout."""
        self.timeout = timeout

    def run_command(
        self, repo_path: Path, command: str, args: Optional[list[str]] = None
    ) -> GitTidyResult:
        """Execute a git-tidy command and capture results."""
        if args is None:
            args = []

        # Build the full command
        cmd_args = ["uv", "run", "git-tidy", command] + args

        # Start timing
        import time

        start_time = time.time()

        try:
            # Execute the command
            result = subprocess.run(
                cmd_args,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            execution_time = time.time() - start_time

            return GitTidyResult(
                command=command,
                args=args,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time,
                repo_path=repo_path,
            )

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return GitTidyResult(
                command=command,
                args=args,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {self.timeout} seconds",
                execution_time=execution_time,
                repo_path=repo_path,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return GitTidyResult(
                command=command,
                args=args,
                exit_code=-2,
                stdout="",
                stderr=f"Execution failed: {str(e)}",
                execution_time=execution_time,
                repo_path=repo_path,
            )

    def run_with_dry_run(
        self, repo_path: Path, command: str, args: list[str]
    ) -> GitTidyResult:
        """Run command with dry-run flag if supported."""
        # Add --dry-run if command supports it
        dry_run_commands = {"group-commits", "split-commits"}

        if command in dry_run_commands:
            dry_run_args = args + ["--dry-run"]
        else:
            # For commands that use --apply, don't add --apply (defaults to preview)
            dry_run_args = [arg for arg in args if arg != "--apply"]

        return self.run_command(repo_path, command, dry_run_args)

    def run_and_apply(
        self, repo_path: Path, command: str, args: list[str]
    ) -> GitTidyResult:
        """Run command with apply/no-prompt flags for actual execution."""
        # Commands that use --apply
        apply_commands = {"smart-merge", "smart-revert"}
        # Commands that use --no-prompt
        prompt_commands = {
            "smart-rebase",
            "rebase-skip-merged",
            "group-commits",
            "split-commits",
        }

        if command in apply_commands:
            apply_args = args + ["--apply", "--no-prompt"]
        elif command in prompt_commands:
            apply_args = args + ["--no-prompt"]
        else:
            # Remove dry-run for other commands
            apply_args = [arg for arg in args if arg not in ["--dry-run"]]

        return self.run_command(repo_path, command, apply_args)

    def is_success(self, result: GitTidyResult) -> bool:
        """Check if command execution was successful."""
        return result.exit_code == 0

    def has_changes_indicated(self, result: GitTidyResult) -> bool:
        """Check if the command output indicates changes would be made."""
        # Look for common indicators of planned changes
        change_indicators = [
            "would reorder",
            "would split",
            "would merge",
            "would revert",
            "would rebase",
            "would group",  # For group-commits
            "would create",  # For split-commits output like "Would create 2 separate commits"
            "changes to be made",
            "commits to process",
            "group into",  # For group-commits output like "would group into 3 groups"
        ]

        output_text = (result.stdout + result.stderr).lower()
        return any(indicator in output_text for indicator in change_indicators)

    def has_conflicts_reported(self, result: GitTidyResult) -> bool:
        """Check if the command output indicates conflicts."""
        conflict_indicators = [
            "conflict",
            "merge conflict",
            "unable to merge",
            "conflicting changes",
        ]

        output_text = (result.stdout + result.stderr).lower()
        return any(indicator in output_text for indicator in conflict_indicators)
