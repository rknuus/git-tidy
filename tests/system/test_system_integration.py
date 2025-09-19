"""Integration tests demonstrating the system test framework."""

import tempfile
from pathlib import Path

import pytest

from tests.test_repository_fixtures import TestRepositoryFixtures

from .framework.git_tidy_runner import ExpectedOutcome, GitTidyRunner
from .framework.result_validator import RepositoryState, ResultValidator


class TestSystemIntegration:
    """Integration tests demonstrating system test framework functionality."""

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
    def test_system_framework_basic_functionality(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test that the system test framework works correctly."""
        # Create a test repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Verify repository was created correctly
        assert repo_path.exists()
        assert (repo_path / ".git").exists()

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Verify we can capture repository state
        assert not pre_state.is_empty
        assert pre_state.commit_count == 5  # linear_simple has 5 commits
        assert "main" in pre_state.branches

        # Run a git-tidy command that should work
        result = runner.run_command(repo_path, "--help", [])

        # Verify command execution works
        assert result.exit_code == 0
        assert "git-tidy" in result.stdout.lower()

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Help command shouldn't change repository
        assert pre_state.head_sha == post_state.head_sha
        assert pre_state.commit_count == post_state.commit_count

    @pytest.mark.fast
    def test_git_tidy_version_command(
        self, temp_dir: Path, runner: GitTidyRunner
    ) -> None:
        """Test git-tidy version command."""
        # Create any repository for context
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_single_commit(temp_dir)

        # Run version command
        result = runner.run_command(repo_path, "--version", [])

        # Should succeed and show version info
        assert result.exit_code == 0
        # Version output should contain some version information
        assert len(result.stdout.strip()) > 0 or len(result.stderr.strip()) > 0

    @pytest.mark.fast
    def test_git_tidy_help_subcommand(
        self, temp_dir: Path, runner: GitTidyRunner
    ) -> None:
        """Test git-tidy help for specific subcommands."""
        # Create any repository for context
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Test help for group-commits command
        result = runner.run_command(repo_path, "group-commits", ["--help"])

        # Should succeed and show help
        assert result.exit_code == 0
        help_text = result.stdout.lower()
        assert "group" in help_text or "commit" in help_text

    @pytest.mark.fast
    def test_repository_state_comparison(self, temp_dir: Path) -> None:
        """Test repository state comparison functionality."""
        # Create repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_feature_branch(temp_dir)

        # Capture initial state
        state1 = RepositoryState(repo_path)

        # Create another repository of same type
        repo_path2 = fixtures.create_repo_feature_branch(temp_dir / "repo2")
        state2 = RepositoryState(repo_path2)

        # States should be similar but not identical (different paths, same structure)
        assert state1.commit_count == state2.commit_count
        assert state1.branches == state2.branches
        assert state1.is_empty == state2.is_empty

    @pytest.mark.fast
    def test_validation_framework_error_detection(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test that validation framework can detect errors properly."""
        # Create repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Capture state
        pre_state = RepositoryState(repo_path)

        # Run command that should fail (invalid subcommand)
        result = runner.run_command(repo_path, "nonexistent-command", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should detect error
        assert result.exit_code != 0

        # Repository should be unchanged
        assert pre_state.head_sha == post_state.head_sha
        assert pre_state.commit_count == post_state.commit_count

        # Validation should work
        validator.validate_result(
            result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state
        )

    @pytest.mark.fast
    def test_multiple_repository_types_framework(self, temp_dir: Path) -> None:
        """Test framework with multiple repository types."""
        fixtures = TestRepositoryFixtures()

        # Create different repository types
        repos = {
            "linear": fixtures.create_repo_linear_simple(temp_dir / "linear"),
            "feature": fixtures.create_repo_feature_branch(temp_dir / "feature"),
            "empty": fixtures.create_repo_no_commits(temp_dir / "empty"),
        }

        # Verify all repositories are created and accessible
        for repo_name, repo_path in repos.items():
            assert repo_path.exists(), f"Repository {repo_name} should exist"

            state = RepositoryState(repo_path)

            if repo_name == "empty":
                assert state.is_empty, f"Repository {repo_name} should be empty"
            else:
                assert not state.is_empty, f"Repository {repo_name} should not be empty"
                assert (
                    state.commit_count > 0
                ), f"Repository {repo_name} should have commits"
