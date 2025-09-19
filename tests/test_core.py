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

    @patch("os.path.exists")
    @patch.object(GitTidy, "run_git")
    def test_restore_from_backup(self, mock_run_git, mock_exists):
        """Test restore from backup."""
        self.git_tidy.backup_branch = "backup-abcd1234"
        self.git_tidy.original_head = "abcd1234567890"

        # Mock git status to return success but no rebase in progress
        mock_run_git.return_value.returncode = 0
        mock_exists.return_value = False

        with patch("builtins.print"):
            self.git_tidy.restore_from_backup()

        assert mock_run_git.call_count == 3  # status, reset, branch delete
        mock_run_git.assert_any_call(["status", "--porcelain=v1"], check_output=False)
        mock_run_git.assert_any_call(["reset", "--hard", "abcd1234567890"])
        mock_run_git.assert_any_call(
            ["branch", "-D", "backup-abcd1234"], check_output=False
        )

    @patch("os.path.exists")
    @patch.object(GitTidy, "run_git")
    def test_restore_from_backup_with_rebase_in_progress(
        self, mock_run_git, mock_exists
    ):
        """Test restore from backup when rebase is in progress."""
        self.git_tidy.backup_branch = "backup-abcd1234"
        self.git_tidy.original_head = "abcd1234567890"

        # Mock git status to return success and rebase in progress
        mock_run_git.return_value.returncode = 0
        mock_exists.return_value = True

        with patch("builtins.print"):
            self.git_tidy.restore_from_backup()

        assert (
            mock_run_git.call_count == 4
        )  # status, rebase abort, reset, branch delete
        mock_run_git.assert_any_call(["status", "--porcelain=v1"], check_output=False)
        mock_run_git.assert_any_call(["rebase", "--abort"], check_output=False)
        mock_run_git.assert_any_call(["reset", "--hard", "abcd1234567890"])
        mock_run_git.assert_any_call(
            ["branch", "-D", "backup-abcd1234"], check_output=False
        )

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

    def test_get_commit_message(self):
        """Test getting commit message."""
        mock_output = "Fix bug in authentication\n\nThis commit fixes a critical bug\nin the JWT authentication system.\n\nCloses #123"

        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            mock_run_git.return_value = Mock(stdout=mock_output)
            message = self.git_tidy.get_commit_message("abc123")

        assert message == mock_output
        mock_run_git.assert_called_once_with(
            ["show", "--pretty=format:%B", "--no-patch", "abc123"]
        )

    def test_get_commit_message_empty(self):
        """Test getting commit message from empty commit."""
        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            mock_run_git.return_value = Mock(stdout="")
            message = self.git_tidy.get_commit_message("abc123")

        assert message == ""

    @patch("builtins.input")
    @patch.object(GitTidy, "run_git")
    def test_perform_split_rebase_no_splitting_needed(self, mock_run_git, mock_input):
        """Test perform_split_rebase when no commits need splitting."""
        commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
            {"sha": "def456", "subject": "Fix bug 2", "files": {"file2.py"}},
        ]

        result = self.git_tidy.perform_split_rebase(commits)

        assert result is True
        mock_input.assert_not_called()  # Should not ask for confirmation
        mock_run_git.assert_not_called()  # Should not perform any git operations

    @patch("builtins.input")
    @patch.object(GitTidy, "run_git")
    def test_perform_split_rebase_user_cancels(self, mock_run_git, mock_input):
        """Test perform_split_rebase when user cancels."""
        commits = [
            {
                "sha": "abc123",
                "subject": "Fix bug 1",
                "files": {"file1.py", "file2.py"},
            },
        ]

        mock_input.return_value = "n"  # User cancels
        mock_run_git.side_effect = [
            Mock(stdout="base123"),  # rev-parse for base commit
        ]

        result = self.git_tidy.perform_split_rebase(commits)

        assert result is False
        mock_input.assert_called_once_with("\nProceed with split rebase? (y/N): ")
        # Should not proceed with reset or commit operations

    @patch("builtins.input")
    @patch.object(GitTidy, "run_git")
    @patch.object(GitTidy, "get_commit_message")
    def test_perform_split_rebase_success(
        self, mock_get_message, mock_run_git, mock_input
    ):
        """Test successful perform_split_rebase."""
        commits = [
            {
                "sha": "abc123",
                "subject": "Fix bug 1",
                "files": {"file1.py", "file2.py"},
            },
            {"sha": "def456", "subject": "Fix bug 2", "files": {"file3.py"}},
        ]

        mock_input.return_value = "y"  # User confirms
        mock_get_message.side_effect = [
            "Fix bug 1\n\nOriginal message",
            "Fix bug 2\n\nAnother message",
        ]
        mock_run_git.side_effect = [
            Mock(stdout="base123"),  # rev-parse for base commit
            Mock(),  # reset --soft
            Mock(),  # cherry-pick --no-commit
            Mock(),  # reset HEAD
            Mock(),  # add file1.py
            Mock(),  # commit file1.py
            Mock(),  # cherry-pick --no-commit
            Mock(),  # reset HEAD
            Mock(),  # add file2.py
            Mock(),  # commit file2.py
            Mock(),  # cherry-pick --no-commit
            Mock(),  # reset HEAD
            Mock(),  # add file3.py
            Mock(),  # commit file3.py
        ]

        with patch("builtins.print") as mock_print:
            result = self.git_tidy.perform_split_rebase(commits)

        assert result is True
        mock_input.assert_called_once_with("\nProceed with split rebase? (y/N): ")

        # Verify git operations were called
        assert mock_run_git.call_count == 14  # All expected calls
        mock_run_git.assert_any_call(["rev-parse", "abc123^"])
        mock_run_git.assert_any_call(["reset", "--soft", "base123"])

        # Verify print statements
        mock_print.assert_any_call("Splitting 2 commits into 3 file-based commits...")
        mock_print.assert_any_call("Successfully created 3 commits:")

    @patch("builtins.input")
    @patch.object(GitTidy, "run_git")
    @patch.object(GitTidy, "get_commit_message")
    def test_perform_split_rebase_empty_commit(
        self, mock_get_message, mock_run_git, mock_input
    ):
        """Test perform_split_rebase with empty commit."""
        commits = [
            {"sha": "abc123", "subject": "Empty commit", "files": set()},
        ]

        with patch("builtins.print") as mock_print:
            result = self.git_tidy.perform_split_rebase(commits)

        assert result is True
        # Empty commits are considered as "no splitting needed" since len(files) <= 1
        mock_input.assert_not_called()  # Should not ask for confirmation
        mock_run_git.assert_not_called()  # Should not perform any git operations
        mock_print.assert_called_with(
            "No commits need splitting - all commits already have single files"
        )

    @patch.object(GitTidy, "run_git")
    def test_configure_repo_dry_run(self, mock_run_git):
        """Test configure_repo dry-run prints planned changes."""
        options = {"scope": "local", "preset": "safe", "dry_run": True}

        with patch("builtins.print") as mock_print:
            self.git_tidy.configure_repo(options)

        # Should not execute any git commands
        mock_run_git.assert_not_called()
        # Should print a header line
        mock_print.assert_any_call("Planned git configuration changes:")

    @patch.object(GitTidy, "run_git")
    def test_configure_repo_executes(self, mock_run_git):
        """Test configure_repo applies settings using git config."""
        options = {"scope": "local", "preset": "safe", "dry_run": False}

        self.git_tidy.configure_repo(options)

        # Expect multiple config calls, at least one with rerere.enabled
        assert mock_run_git.call_count >= 1
        calls = [args[0][0] for args in mock_run_git.call_args_list]
        assert any(call[:2] == ["config", "--local"] for call in calls)

    @patch.object(GitTidy, "perform_split_rebase")
    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "cleanup_backup")
    def test_split_commits_success(
        self, mock_cleanup, mock_backup, mock_get_commits, mock_perform
    ):
        """Test successful split_commits execution."""
        mock_commits = [
            {
                "sha": "abc123",
                "subject": "Fix bug 1",
                "files": {"file1.py", "file2.py"},
            },
        ]
        mock_get_commits.return_value = mock_commits
        mock_perform.return_value = True

        self.git_tidy.split_commits("HEAD~5")

        mock_backup.assert_called_once()
        mock_get_commits.assert_called_once_with("HEAD~5")
        mock_perform.assert_called_once_with(mock_commits)
        mock_cleanup.assert_called_once()

    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "cleanup_backup")
    def test_split_commits_no_commits(
        self, mock_cleanup, mock_backup, mock_get_commits
    ):
        """Test split_commits when no commits found."""
        mock_get_commits.return_value = []

        with patch("builtins.print") as mock_print:
            self.git_tidy.split_commits()

        mock_backup.assert_called_once()
        mock_get_commits.assert_called_once_with(None)
        mock_print.assert_called_with("No commits found to split")
        mock_cleanup.assert_called_once()

    @patch.object(GitTidy, "perform_split_rebase")
    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "restore_from_backup")
    def test_split_commits_failure(
        self, mock_restore, mock_backup, mock_get_commits, mock_perform
    ):
        """Test split_commits when perform_split_rebase fails."""
        mock_commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
        ]
        mock_get_commits.return_value = mock_commits
        mock_perform.return_value = False

        self.git_tidy.split_commits()

        mock_backup.assert_called_once()
        mock_get_commits.assert_called_once_with(None)
        mock_perform.assert_called_once_with(mock_commits)
        mock_restore.assert_called_once()

    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "restore_from_backup")
    def test_split_commits_exception(self, mock_restore, mock_backup, mock_get_commits):
        """Test split_commits when exception occurs."""
        mock_get_commits.side_effect = Exception("Git error")

        with patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit):
                self.git_tidy.split_commits()

        mock_backup.assert_called_once()
        mock_get_commits.assert_called_once_with(None)
        mock_restore.assert_called_once()
        mock_print.assert_called_with("Error: Git error")
