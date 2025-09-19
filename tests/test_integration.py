"""Integration tests for git-tidy."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from git_tidy.core import GitError, GitTidy


class TestGitTidyIntegration:
    """Integration tests for GitTidy workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.git_tidy = GitTidy()

    @patch.object(GitTidy, "run_git")
    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_perform_rebase_success(self, mock_unlink, mock_temp_file, mock_run_git):
        """Test successful rebase operation."""
        # Setup mocks
        mock_file = Mock()
        mock_file.name = "/tmp/test_todo"
        mock_temp_file.return_value.__enter__.return_value = mock_file

        mock_run_git.side_effect = [
            Mock(stdout="base123"),  # rev-parse for base commit
            Mock(returncode=0),  # rebase command success
        ]

        groups = [
            [
                {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
                {"sha": "def456", "subject": "Fix bug 2", "files": {"file1.py"}},
            ],
            [
                {"sha": "ghi789", "subject": "Fix bug 3", "files": {"file2.py"}},
            ],
        ]

        with patch("builtins.input", return_value="y"):
            with patch("builtins.print"):
                result = self.git_tidy.perform_rebase(groups)

        assert result is True
        mock_unlink.assert_called_once_with("/tmp/test_todo")

    @patch.object(GitTidy, "run_git")
    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_perform_rebase_failure(self, mock_unlink, mock_temp_file, mock_run_git):
        """Test rebase operation failure."""
        # Setup mocks
        mock_file = Mock()
        mock_file.name = "/tmp/test_todo"
        mock_temp_file.return_value.__enter__.return_value = mock_file

        # First call returns base commit, second call returns failed result
        base_result = Mock()
        base_result.stdout = "base123"

        rebase_result = Mock()
        rebase_result.returncode = 1
        rebase_result.stderr = "Rebase conflict"

        mock_run_git.side_effect = [base_result, rebase_result]

        # Need multiple groups to trigger rebase logic
        groups = [
            [{"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}}],
            [{"sha": "def456", "subject": "Fix bug 2", "files": {"file2.py"}}],
        ]

        with patch("builtins.input", return_value="y"):
            with patch("builtins.print"):
                result = self.git_tidy.perform_rebase(groups)

        assert result is False
        mock_unlink.assert_called_once_with("/tmp/test_todo")

    @patch.object(GitTidy, "run_git")
    def test_perform_rebase_cancelled(self, mock_run_git):
        """Test rebase operation cancelled by user."""
        # Need multiple groups to trigger rebase logic
        groups = [
            [{"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}}],
            [{"sha": "def456", "subject": "Fix bug 2", "files": {"file2.py"}}],
        ]

        base_result = Mock()
        base_result.stdout = "base123"
        mock_run_git.return_value = base_result

        with patch("builtins.input", return_value="n"):
            with patch("builtins.print"):
                result = self.git_tidy.perform_rebase(groups)

        assert result is False
        # Should not have called rebase command
        assert mock_run_git.call_count == 1  # Only rev-parse call

    def test_perform_rebase_single_group(self):
        """Test rebase with single group (no rebase needed)."""
        groups = [[{"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}}]]

        with patch("builtins.print") as mock_print:
            result = self.git_tidy.perform_rebase(groups)

        assert result is True
        mock_print.assert_called_with(
            "No grouping needed - commits are already optimally ordered"
        )

    def test_perform_rebase_empty_groups(self):
        """Test rebase with empty groups."""
        groups = []

        with patch("builtins.print") as mock_print:
            result = self.git_tidy.perform_rebase(groups)

        assert result is True
        mock_print.assert_called_with(
            "No grouping needed - commits are already optimally ordered"
        )

    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "group_commits")
    @patch.object(GitTidy, "perform_rebase")
    @patch.object(GitTidy, "cleanup_backup")
    def test_run_success(
        self, mock_cleanup, mock_rebase, mock_group, mock_get_commits, mock_backup
    ):
        """Test successful run workflow."""
        mock_commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
        ]
        mock_groups = [mock_commits]

        mock_get_commits.return_value = mock_commits
        mock_group.return_value = mock_groups
        mock_rebase.return_value = True

        with patch("builtins.print"):
            self.git_tidy.run("origin/main", 0.5)

        mock_backup.assert_called_once()
        mock_get_commits.assert_called_once_with("origin/main")
        mock_group.assert_called_once_with(mock_commits, 0.5)
        mock_rebase.assert_called_once_with(mock_groups, no_prompt=False)
        mock_cleanup.assert_called_once()

    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "restore_from_backup")
    def test_run_no_commits(self, mock_restore, mock_get_commits, mock_backup):
        """Test run workflow with no commits."""
        mock_get_commits.return_value = []

        with patch("builtins.print") as mock_print:
            self.git_tidy.run()

        mock_backup.assert_called_once()
        mock_get_commits.assert_called_once_with(None)
        mock_print.assert_called_with("No commits found to rebase")
        mock_restore.assert_not_called()

    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "group_commits")
    @patch.object(GitTidy, "perform_rebase")
    @patch.object(GitTidy, "restore_from_backup")
    def test_run_rebase_failure(
        self, mock_restore, mock_rebase, mock_group, mock_get_commits, mock_backup
    ):
        """Test run workflow when rebase fails."""
        mock_commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
        ]
        mock_groups = [mock_commits]

        mock_get_commits.return_value = mock_commits
        mock_group.return_value = mock_groups
        mock_rebase.return_value = False

        with patch("builtins.print"):
            self.git_tidy.run()

        mock_restore.assert_called_once()

    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "restore_from_backup")
    @patch("sys.exit")
    def test_run_exception_handling(self, mock_exit, mock_restore, mock_backup):
        """Test run workflow exception handling."""
        mock_backup.side_effect = Exception("Test error")

        with patch("builtins.print") as mock_print:
            self.git_tidy.run()

        mock_restore.assert_called_once()
        mock_exit.assert_called_once_with(1)
        mock_print.assert_called_with("Error: Test error")


class TestGitTidyErrorHandling:
    """Test error handling scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.git_tidy = GitTidy()

    def test_git_error_exception(self):
        """Test GitError exception properties."""
        error = GitError("Test error message")
        assert str(error) == "Test error message"

    @patch("subprocess.run")
    def test_run_git_subprocess_error_with_stderr(self, mock_run):
        """Test run_git with subprocess error that has stderr."""
        error = subprocess.CalledProcessError(1, ["git", "status"])
        error.stderr = "fatal: not a git repository"
        mock_run.side_effect = error

        with pytest.raises(GitError) as exc_info:
            self.git_tidy.run_git(["status"])

        assert "Git command failed: status" in str(exc_info.value)
        assert "fatal: not a git repository" in str(exc_info.value)

    @patch("subprocess.run")
    def test_run_git_subprocess_error_no_stderr(self, mock_run):
        """Test run_git with subprocess error that has no stderr."""
        error = subprocess.CalledProcessError(1, ["git", "status"])
        error.stderr = None
        mock_run.side_effect = error

        with pytest.raises(GitError) as exc_info:
            self.git_tidy.run_git(["status"])

        assert "Git command failed: status" in str(exc_info.value)
        assert "None" in str(exc_info.value)

    def test_restore_from_backup_missing_info(self):
        """Test restore from backup with missing information."""
        # Test with missing backup_branch
        self.git_tidy.original_head = "abc123"
        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            self.git_tidy.restore_from_backup()
        mock_run_git.assert_not_called()

        # Test with missing original_head
        self.git_tidy.backup_branch = "backup-abc123"
        self.git_tidy.original_head = None
        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            self.git_tidy.restore_from_backup()
        mock_run_git.assert_not_called()

    @patch.object(GitTidy, "run_git")
    def test_get_commits_to_rebase_with_custom_base(self, mock_run_git):
        """Test get_commits_to_rebase with custom base reference."""
        mock_run_git.return_value = Mock(stdout="abc123|Fix bug 1")

        with patch.object(self.git_tidy, "get_commit_files") as mock_get_files:
            mock_get_files.return_value = {"file1.py"}
            self.git_tidy.get_commits_to_rebase("custom-base")

        expected_range = "custom-base..HEAD"
        mock_run_git.assert_called_once_with(
            ["log", expected_range, "--pretty=format:%H|%s", "--reverse"]
        )

    def test_calculate_similarity_edge_cases(self):
        """Test calculate_similarity with edge cases."""
        # Both empty sets
        assert self.git_tidy.calculate_similarity(set(), set()) == 1.0

        # One empty set
        assert self.git_tidy.calculate_similarity({"file1.py"}, set()) == 0.0
        assert self.git_tidy.calculate_similarity(set(), {"file1.py"}) == 0.0

        # Normal case for completeness
        files1 = {"file1.py", "file2.py"}
        files2 = {"file1.py", "file3.py"}
        expected = 1 / 3  # intersection: 1, union: 3
        assert self.git_tidy.calculate_similarity(files1, files2) == expected
