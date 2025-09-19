"""System tests for git-tidy split-commits command."""

import tempfile
from pathlib import Path

import pytest

from tests.test_repository_fixtures import TestRepositoryFixtures
from tests.test_advanced_repository_fixtures import TestAdvancedRepositoryFixtures

from .framework.git_tidy_runner import ExpectedOutcome, GitTidyRunner
from .framework.result_validator import RepositoryState, ResultValidator


class TestSplitCommitsSystem:
    """System tests for split-commits command."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for repositories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    @pytest.fixture
    def runner(self) -> GitTidyRunner:
        """Create a git-tidy command runner."""
        return GitTidyRunner(timeout=30)

    @pytest.fixture
    def validator(self) -> ResultValidator:
        """Create a result validator."""
        return ResultValidator()

    @pytest.mark.fast
    def test_split_commits_split_targets_preview(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on split_targets repository in preview mode."""
        # Create repository with multi-file commits
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_split_targets(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits in dry-run mode
        result = runner.run_with_dry_run(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Validate preview mode - no changes should be made
        validator.validate_result(result, ExpectedOutcome.PREVIEW_ONLY, pre_state, post_state)

        # Should indicate changes would be made
        assert runner.has_changes_indicated(result), "Expected preview to show changes would be made"

    @pytest.mark.fast
    def test_split_commits_split_targets_apply(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on split_targets repository with actual changes."""
        # Create repository with multi-file commits
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_split_targets(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits to apply changes
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Validate successful execution with changes
        validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

        # Commit count should increase (splitting commits creates more commits)
        assert post_state.commit_count > pre_state.commit_count, "Expected more commits after splitting"

        # Backup branch should be created
        validator.validate_backup_created(repo_path, expected=True)

    @pytest.mark.fast
    def test_split_commits_merge_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on repository with merge commits."""
        # Create repository with merge commits
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_merge_commits(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed (may or may not have changes depending on commit structure)
        if runner.has_changes_indicated(result):
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_split_commits_with_base(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits with custom base commit."""
        # Create repository with split targets
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_split_targets(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits with base specification
        result = runner.run_and_apply(repo_path, "split-commits", ["--base", "HEAD~2"])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed
        if runner.has_changes_indicated(result):
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_split_commits_single_file_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on repository with single-file commits."""
        # Create repository where commits already touch single files
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed but make no changes (already single-file commits)
        validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_split_commits_insufficient_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on repository with insufficient commits."""
        # Create repository with only one commit
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_single_commit(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should either succeed with no changes or fail gracefully
        if result.exit_code == 0:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)

    @pytest.mark.fast
    def test_split_commits_empty_repository(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on empty repository."""
        # Create empty repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_no_commits(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should fail gracefully on empty repository
        validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)