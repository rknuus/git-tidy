"""Tests for git-tidy core functionality."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from git_tidy.core import GitError, GitTidy


def test_calculate_similarity():
    """Test file similarity calculation."""
    git_tidy = GitTidy()

    # Identical sets
    files1 = {"file1.py", "file2.py"}
    files2 = {"file1.py", "file2.py"}
    assert git_tidy.calculate_similarity(files1, files2) == 1.0

    # No overlap
    files1 = {"file1.py", "file2.py"}
    files2 = {"file3.py", "file4.py"}
    assert git_tidy.calculate_similarity(files1, files2) == 0.0

    # Partial overlap
    files1 = {"file1.py", "file2.py"}
    files2 = {"file1.py", "file3.py"}
    expected = 1 / 3  # intersection: 1, union: 3
    assert git_tidy.calculate_similarity(files1, files2) == expected

    # Empty sets
    assert git_tidy.calculate_similarity(set(), set()) == 1.0
    assert git_tidy.calculate_similarity({"file1.py"}, set()) == 0.0


def test_describe_group():
    """Test group description generation."""
    git_tidy = GitTidy()

    # Small group
    group = [
        {"files": {"file1.py", "file2.py"}},
        {"files": {"file1.py", "file3.py"}},
    ]
    description = git_tidy.describe_group(group)
    assert "file1.py" in description
    assert "file2.py" in description
    assert "file3.py" in description

    # Large group (should truncate)
    files = {f"file{i}.py" for i in range(10)}
    group = [{"files": files}]
    description = git_tidy.describe_group(group)
    assert "more" in description


def test_group_commits():
    """Test commit grouping logic."""
    git_tidy = GitTidy()

    commits = [
        {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py", "file2.py"}},
        {"sha": "def456", "subject": "Fix bug 2", "files": {"file3.py", "file4.py"}},
        {"sha": "ghi789", "subject": "Fix bug 3", "files": {"file1.py", "file5.py"}},
    ]

    # High threshold should keep commits separate
    groups = git_tidy.group_commits(commits, similarity_threshold=0.8)
    assert len(groups) == 3

    # Low threshold should group similar commits
    groups = git_tidy.group_commits(commits, similarity_threshold=0.1)
    # First and third commits share file1.py, so they should be grouped
    assert len(groups) == 2
    assert len(groups[0]) == 2  # First group has 2 commits
    assert len(groups[1]) == 1  # Second group has 1 commit


class TestGitTidy:
    """Test class for GitTidy functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.git_tidy = GitTidy()

    def test_init(self):
        """Test GitTidy initialization."""
        assert self.git_tidy.original_branch is None
        assert self.git_tidy.original_head is None
        assert self.git_tidy.backup_branch is None

    @patch("subprocess.run")
    def test_run_git_success(self, mock_run):
        """Test successful git command execution."""
        mock_result = Mock()
        mock_result.stdout = "test output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = self.git_tidy.run_git(["status"])

        assert result == mock_result
        mock_run.assert_called_once_with(
            ["git", "status"], capture_output=True, text=True, check=True, env=None
        )

    @patch("subprocess.run")
    def test_run_git_failure(self, mock_run):
        """Test git command failure handling."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git status", stderr="error message"
        )

        with pytest.raises(GitError) as exc_info:
            self.git_tidy.run_git(["status"])

        assert "Git command failed: status" in str(exc_info.value)
        assert "error message" in str(exc_info.value)

    @patch("subprocess.run")
    def test_run_git_no_check_output(self, mock_run):
        """Test git command with check_output=False."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = self.git_tidy.run_git(["status"], check_output=False)

        assert result == mock_result
        mock_run.assert_called_once_with(
            ["git", "status"], capture_output=True, text=True, check=False, env=None
        )

    @patch.object(GitTidy, "run_git")
    def test_create_backup(self, mock_run_git):
        """Test backup creation."""
        mock_run_git.side_effect = [
            Mock(stdout="main"),  # branch --show-current
            Mock(stdout="abcd1234567890"),  # rev-parse HEAD
            Mock(),  # branch backup-abcd1234 HEAD
        ]

        with patch("builtins.print") as mock_print:
            self.git_tidy.create_backup()

        assert self.git_tidy.original_branch == "main"
        assert self.git_tidy.original_head == "abcd1234567890"
        assert self.git_tidy.backup_branch == "backup-abcd1234"
        mock_print.assert_called_once_with("Created backup branch: backup-abcd1234")

    @patch.object(GitTidy, "run_git")
    def test_restore_from_backup(self, mock_run_git):
        """Test restore from backup."""
        self.git_tidy.backup_branch = "backup-abcd1234"
        self.git_tidy.original_head = "abcd1234567890"

        with patch("builtins.print") as mock_print:
            self.git_tidy.restore_from_backup()

        assert mock_run_git.call_count == 2
        mock_run_git.assert_any_call(["reset", "--hard", "abcd1234567890"])
        mock_run_git.assert_any_call(
            ["branch", "-D", "backup-abcd1234"], check_output=False
        )
        mock_print.assert_called_once_with("Restoring from backup due to error...")

    @patch.object(GitTidy, "run_git")
    def test_cleanup_backup(self, mock_run_git):
        """Test backup cleanup."""
        self.git_tidy.backup_branch = "backup-abcd1234"

        with patch("builtins.print") as mock_print:
            self.git_tidy.cleanup_backup()

        mock_run_git.assert_called_once_with(
            ["branch", "-D", "backup-abcd1234"], check_output=False
        )
        mock_print.assert_called_once_with("Cleaned up backup branch: backup-abcd1234")

    def test_cleanup_backup_no_branch(self):
        """Test cleanup when no backup branch exists."""
        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            self.git_tidy.cleanup_backup()

        mock_run_git.assert_not_called()

    def test_get_commit_files(self):
        """Test getting files from a commit."""
        mock_output = "\nfile1.py\nfile2.py\n\n"

        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            mock_run_git.return_value = Mock(stdout=mock_output)
            files = self.git_tidy.get_commit_files("abc123")

        assert files == {"file1.py", "file2.py"}
        mock_run_git.assert_called_once_with(
            ["show", "--name-only", "--pretty=format:", "abc123"]
        )

    def test_get_commit_files_empty(self):
        """Test getting files from a commit with no files."""
        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            mock_run_git.return_value = Mock(stdout="\n\n")
            files = self.git_tidy.get_commit_files("abc123")

        assert files == set()

    @patch.object(GitTidy, "get_commit_files")
    @patch.object(GitTidy, "run_git")
    def test_get_commits_to_rebase_with_main(self, mock_run_git, mock_get_files):
        """Test getting commits to rebase with main branch."""
        mock_run_git.side_effect = [
            Mock(stdout="base123"),  # merge-base with main
            Mock(stdout="abc123|Fix bug 1\ndef456|Fix bug 2"),  # log output
        ]
        mock_get_files.side_effect = [
            {"file1.py", "file2.py"},
            {"file3.py"},
        ]

        commits = self.git_tidy.get_commits_to_rebase()

        assert len(commits) == 2
        assert commits[0]["sha"] == "abc123"
        assert commits[0]["subject"] == "Fix bug 1"
        assert commits[0]["files"] == {"file1.py", "file2.py"}
        assert commits[1]["sha"] == "def456"
        assert commits[1]["subject"] == "Fix bug 2"

    @patch.object(GitTidy, "get_commit_files")
    @patch.object(GitTidy, "run_git")
    def test_get_commits_to_rebase_fallback_master(self, mock_run_git, mock_get_files):
        """Test getting commits to rebase falling back to master."""

        def side_effect(cmd, **kwargs):
            if "main" in cmd:
                raise GitError("No main branch")
            elif "master" in cmd:
                return Mock(stdout="base456")
            else:
                return Mock(stdout="abc123|Fix bug 1")

        mock_run_git.side_effect = side_effect
        mock_get_files.return_value = {"file1.py"}

        commits = self.git_tidy.get_commits_to_rebase()

        assert len(commits) == 1
        assert commits[0]["sha"] == "abc123"

    @patch.object(GitTidy, "get_commit_files")
    @patch.object(GitTidy, "run_git")
    def test_get_commits_to_rebase_fallback_head(self, mock_run_git, mock_get_files):
        """Test getting commits to rebase falling back to HEAD~10."""

        def side_effect(cmd, **kwargs):
            if any(branch in cmd for branch in ["main", "master"]):
                raise GitError("No branch found")
            else:
                return Mock(stdout="abc123|Fix bug 1")

        mock_run_git.side_effect = side_effect
        mock_get_files.return_value = {"file1.py"}

        commits = self.git_tidy.get_commits_to_rebase()

        assert len(commits) == 1
        # Should have called with HEAD~10 range
        expected_range = "HEAD~10..HEAD"
        mock_run_git.assert_any_call(
            ["log", expected_range, "--pretty=format:%H|%s", "--reverse"]
        )

    def test_get_commits_to_rebase_empty(self):
        """Test getting commits when no commits found."""
        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            mock_run_git.side_effect = [
                Mock(stdout="base123"),  # merge-base
                Mock(stdout=""),  # empty log output
            ]

            commits = self.git_tidy.get_commits_to_rebase()

        assert commits == []

    def test_create_rebase_todo(self):
        """Test creating rebase todo list."""
        groups = [
            [
                {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
                {"sha": "def456", "subject": "Fix bug 2", "files": {"file1.py"}},
            ],
            [
                {"sha": "ghi789", "subject": "Fix bug 3", "files": {"file2.py"}},
            ],
        ]

        with patch.object(self.git_tidy, "describe_group") as mock_describe:
            mock_describe.return_value = "Files: file2.py"
            todo = self.git_tidy.create_rebase_todo(groups)

        lines = todo.split("\n")
        assert "pick abc123" in lines[0]
        assert "pick def456" in lines[1]
        assert "# Group 2: Files: file2.py" in lines[2]
        assert "pick ghi789" in lines[3]

        # Verify describe_group was called correctly
        assert mock_describe.call_count == 1  # Only called for second group

    def test_create_rebase_todo_single_group(self):
        """Test creating rebase todo with single group."""
        groups = [[{"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}}]]

        todo = self.git_tidy.create_rebase_todo(groups)

        lines = todo.split("\n")
        assert len(lines) == 1
        assert "pick abc123 Fix bug 1" == lines[0]

    def test_describe_group_large_group(self):
        """Test describing large group with many files."""
        group = [
            {"files": {f"file{i}.py" for i in range(5)}},
        ]

        description = self.git_tidy.describe_group(group)

        assert "and 2 more" in description
        assert "file0.py" in description  # Should show first 3 files

    def test_group_commits_empty_list(self):
        """Test grouping empty commit list."""
        groups = self.git_tidy.group_commits([])
        assert groups == []

    def test_group_commits_single_commit(self):
        """Test grouping single commit."""
        commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
        ]

        groups = self.git_tidy.group_commits(commits)

        assert len(groups) == 1
        assert len(groups[0]) == 1
        assert groups[0][0]["sha"] == "abc123"
