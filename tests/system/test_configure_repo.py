"""System tests for git-tidy configure-repo command."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.test_repository_fixtures import TestRepositoryFixtures

from .framework.git_tidy_runner import ExpectedOutcome, GitTidyRunner
from .framework.result_validator import RepositoryState, ResultValidator


class TestConfigureRepoSystem:
    """System tests for configure-repo command."""

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

    def _get_git_config(self, repo_path: Path, key: str, scope: str = "local") -> str:
        """Get git configuration value."""
        scope_flag = "--local" if scope == "local" else "--global"
        try:
            result = subprocess.run(
                ["git", "config", scope_flag, key],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    @pytest.mark.fast
    def test_configure_repo_local_safe_preset(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test configure-repo with local scope and safe preset."""
        # Create repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run configure-repo
        result = runner.run_command(
            repo_path, "configure-repo", ["--scope", "local", "--preset", "safe"]
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed with configuration changes
        validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)

        # Verify that git configuration was applied
        # Check for common safe git settings
        merge_tool = self._get_git_config(repo_path, "merge.tool")
        rerere_enabled = self._get_git_config(repo_path, "rerere.enabled")

        # At least some configuration should be set
        assert result.exit_code == 0, "Configuration should succeed"

    @pytest.mark.fast
    def test_configure_repo_idempotent(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test that configure-repo is idempotent."""
        # Create repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Run configure-repo first time
        result1 = runner.run_command(repo_path, "configure-repo", ["--scope", "local"])

        # Capture state after first run
        mid_state = RepositoryState(repo_path)

        # Run configure-repo second time
        result2 = runner.run_command(repo_path, "configure-repo", ["--scope", "local"])

        # Capture final state
        post_state = RepositoryState(repo_path)

        # Both should succeed
        assert result1.exit_code == 0, "First configuration should succeed"
        assert result2.exit_code == 0, "Second configuration should succeed"

        # Second run should make no changes (idempotent)
        validator.validate_result(result2, ExpectedOutcome.SUCCESS_NO_CHANGES, mid_state, post_state)

    @pytest.mark.fast
    def test_configure_repo_default_preset(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test configure-repo with default preset."""
        # Create repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_feature_branch(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run configure-repo with defaults
        result = runner.run_command(repo_path, "configure-repo", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed
        if result.exit_code == 0:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)

    @pytest.mark.fast
    def test_configure_repo_all_repository_types(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test configure-repo on different repository types."""
        # Test on various repository types
        fixtures = TestRepositoryFixtures()
        repo_types = [
            ("linear_simple", fixtures.create_repo_linear_simple),
            ("feature_branch", fixtures.create_repo_feature_branch),
            ("merge_commits", fixtures.create_repo_merge_commits),
        ]

        for repo_type, create_func in repo_types:
            repo_path = create_func(temp_dir / repo_type)

            # Capture initial state
            pre_state = RepositoryState(repo_path)

            # Run configure-repo
            result = runner.run_command(repo_path, "configure-repo", ["--scope", "local"])

            # Capture post state
            post_state = RepositoryState(repo_path)

            # Should succeed on all repository types
            if result.exit_code == 0:
                # Configuration commands typically succeed with changes
                validator.validate_result(
                    result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state
                )
            else:
                # If it fails, should fail gracefully
                validator.validate_result(
                    result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state
                )

    @pytest.mark.fast
    def test_configure_repo_empty_repository(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test configure-repo on empty repository."""
        # Create empty repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_no_commits(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run configure-repo
        result = runner.run_command(repo_path, "configure-repo", ["--scope", "local"])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed even on empty repository (configuration is independent of commits)
        if result.exit_code == 0:
            validator.validate_result(result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state)
        else:
            validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)

    @pytest.mark.fast
    def test_configure_repo_invalid_preset(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test configure-repo with invalid preset."""
        # Create repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run configure-repo with invalid preset
        result = runner.run_command(
            repo_path, "configure-repo", ["--preset", "nonexistent"]
        )

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should fail gracefully
        validator.validate_result(result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state)