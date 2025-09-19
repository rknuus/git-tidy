"""System tests for git-tidy smart-merge command."""

import tempfile
from pathlib import Path

import pytest

from tests.test_repository_fixtures import TestRepositoryFixtures
from tests.test_advanced_repository_fixtures import TestAdvancedRepositoryFixtures

from .framework.git_tidy_runner import ExpectedOutcome, GitTidyRunner
from .framework.result_validator import RepositoryState, ResultValidator


class TestSmartMergeSystem:
    """System tests for smart-merge command."""

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
    def test_smart_merge_feature_branch_preview(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge on feature branch in preview mode."""
        # Create repository with feature branch
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_feature_branch(temp_dir)

        # Switch to feature branch to merge into main
        import pygit2
        repo = pygit2.Repository(str(repo_path))
        repo.checkout(repo.branches["feature"])

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge in preview mode (default)
        result = runner.run_command(repo_path, "smart-merge", ["--branch", "feature", "--into", "main"])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Validate preview mode - no changes should be made
        validator.validate_result(result, ExpectedOutcome.PREVIEW_ONLY, pre_state, post_state)

    @pytest.mark.fast
    def test_smart_merge_feature_branch_apply(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge on feature branch with actual merge."""
        # Create repository with feature branch
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_feature_branch(temp_dir)

        # Switch to main branch to receive the merge
        import pygit2
        repo = pygit2.Repository(str(repo_path))
        repo.checkout(repo.branches["main"])

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge to apply changes
        result = runner.run_and_apply(repo_path, "smart-merge", ["--branch", "feature", "--into", "main"])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Validate successful execution with changes
        validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

        # Should have created a merge commit
        assert post_state.commit_count > pre_state.commit_count, "Expected merge commit to be created"

        # Backup branch should be created
        validator.validate_backup_created(repo_path, expected=True)

    @pytest.mark.fast
    def test_smart_merge_simple_conflicts_detection(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge conflict detection on simple conflicts."""
        # Create repository with conflicting branches
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_simple_conflicts(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge between conflicting branches
        result = runner.run_and_apply(
            repo_path, "smart-merge", ["--branch", "conflict-branch-1", "--into", "main"]
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should either succeed or report conflicts gracefully
        if runner.has_conflicts_reported(result):
            validator.validate_result(result, ExpectedOutcome.CONFLICT_REPORTED, pre_state, post_state)
        else:
            # If conflicts were auto-resolved
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_smart_merge_rename_conflicts(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge with rename conflicts."""
        # Create repository with rename conflicts
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_rename_conflicts(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge with rename detection
        result = runner.run_and_apply(
            repo_path,
            "smart-merge",
            ["--branch", "rename1", "--into", "main", "--rename-detect"],
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should handle rename conflicts
        if runner.has_conflicts_reported(result):
            validator.validate_result(result, ExpectedOutcome.CONFLICT_REPORTED, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_smart_merge_delete_modify_conflicts(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge with delete vs modify conflicts."""
        # Create repository with delete-modify conflicts
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_delete_modify_conflicts(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge
        result = runner.run_and_apply(
            repo_path, "smart-merge", ["--branch", "delete", "--into", "modify"]
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should detect and handle delete-modify conflicts
        if runner.has_conflicts_reported(result):
            validator.validate_result(result, ExpectedOutcome.CONFLICT_REPORTED, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_smart_merge_conflict_bias_ours(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge with conflict bias set to 'ours'."""
        # Create repository with conflicts
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_simple_conflicts(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge with conflict bias
        result = runner.run_and_apply(
            repo_path,
            "smart-merge",
            ["--branch", "conflict-branch-1", "--into", "main", "--conflict-bias", "ours"],
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should either auto-resolve or report conflicts
        if result.exit_code == 0:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.CONFLICT_REPORTED, pre_state, post_state)

    @pytest.mark.fast
    def test_smart_merge_optimize_merge_settings(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge with optimized merge settings."""
        # Create repository with feature branch
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_feature_branch(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge with optimization
        result = runner.run_and_apply(
            repo_path,
            "smart-merge",
            ["--branch", "feature", "--into", "main", "--optimize-merge"],
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed
        validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

    @pytest.mark.fast
    def test_smart_merge_invalid_branch(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge with non-existent branch."""
        # Create simple repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge with invalid branch
        result = runner.run_and_apply(
            repo_path, "smart-merge", ["--branch", "nonexistent", "--into", "main"]
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should fail gracefully
        validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)

    @pytest.mark.fast
    def test_smart_merge_same_branch(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test smart-merge trying to merge branch into itself."""
        # Create repository with feature branch
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_feature_branch(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run smart-merge trying to merge main into main
        result = runner.run_and_apply(
            repo_path, "smart-merge", ["--branch", "main", "--into", "main"]
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should either succeed with no changes or fail gracefully
        if result.exit_code == 0:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)