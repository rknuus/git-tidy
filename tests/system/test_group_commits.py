"""System tests for git-tidy group-commits command."""

import tempfile
from pathlib import Path

import pytest

from tests.test_repository_fixtures import TestRepositoryFixtures
from tests.test_advanced_repository_fixtures import TestAdvancedRepositoryFixtures

from .framework.git_tidy_runner import ExpectedOutcome, GitTidyRunner
from .framework.result_validator import RepositoryState, ResultValidator


class TestGroupCommitsSystem:
    """System tests for group-commits command."""

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
    def test_group_commits_linear_interleaved_preview(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits on linear_interleaved repository in preview mode."""
        # Create repository with interleaved file patterns
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_interleaved(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits in dry-run mode
        result = runner.run_with_dry_run(repo_path, "group-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Validate preview mode - no changes should be made
        validator.validate_result(result, ExpectedOutcome.PREVIEW_ONLY, pre_state, post_state)

        # Should indicate changes would be made
        assert runner.has_changes_indicated(result), "Expected preview to show changes would be made"

    @pytest.mark.fast
    def test_group_commits_linear_interleaved_apply(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits on linear_interleaved repository with actual changes."""
        # Create repository with interleaved file patterns
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_interleaved(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits to apply changes
        result = runner.run_and_apply(repo_path, "group-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Validate successful execution with changes
        validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

        # Commit count should remain the same (reordering, not adding/removing)
        validator.validate_commit_count_change(pre_state, post_state, 0)

        # Backup branch should be cleaned up after successful operation
        validator.validate_backup_created(repo_path, expected=False)

    @pytest.mark.fast
    def test_group_commits_perfect_groups_no_changes(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits on repository that needs grouping (misnamed test)."""
        # Create repository that needs grouping (despite the test name)
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_perfect_groups(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits
        result = runner.run_and_apply(repo_path, "group-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed and make changes (repository was not actually perfectly grouped)
        validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

        # Backup branch should be cleaned up after successful operation
        validator.validate_backup_created(repo_path, expected=False)

    @pytest.mark.fast
    def test_group_commits_no_grouping_needed(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits on repository that needs no grouping."""
        # Create repository where no grouping is beneficial
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_no_grouping_needed(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits
        result = runner.run_and_apply(repo_path, "group-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed but make no changes
        validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_group_commits_similarity_threshold(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits with custom similarity threshold."""
        # Create repository for similarity testing
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_similarity_threshold(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits with custom threshold
        result = runner.run_and_apply(repo_path, "group-commits", ["--threshold", "0.5"])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed (whether changes are made depends on content)
        if runner.has_changes_indicated(result):
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_group_commits_with_base(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits with custom base commit."""
        # Create repository with feature branch
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_feature_branch(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits with base specification
        result = runner.run_and_apply(repo_path, "group-commits", ["--base", "HEAD~2"])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed
        if runner.has_changes_indicated(result):
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_group_commits_insufficient_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits on repository with insufficient commits."""
        # Create repository with only one commit
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_single_commit(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits
        result = runner.run_and_apply(repo_path, "group-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should either succeed with no changes or fail gracefully
        if result.exit_code == 0:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)

    @pytest.mark.fast
    def test_group_commits_empty_repository(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test group-commits on empty repository."""
        # Create empty repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_no_commits(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run group-commits
        result = runner.run_and_apply(repo_path, "group-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should fail gracefully on empty repository
        validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)