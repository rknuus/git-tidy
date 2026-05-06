"""Tests for git-tidy core functionality."""

import subprocess
from pathlib import Path
from typing import Any, Optional
from unittest.mock import Mock, patch

import pygit2
import pytest

from git_tidy.core import GitError, GitTidy

from .test_repository_fixtures import RepositoryBuilder


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
            Mock(stdout="feature"),  # branch --show-current (feature branch)
            Mock(stdout="base123"),  # merge-base with main
            Mock(stdout="head456"),  # rev-parse HEAD (different from base)
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
        """Test getting commits to rebase falling back to HEAD~9."""

        def side_effect(cmd, **kwargs):
            if cmd == ["branch", "--show-current"]:
                return Mock(stdout="feature")
            elif "merge-base" in cmd:
                raise GitError("No branch found")
            elif cmd == ["rev-list", "--count", "HEAD"]:
                return Mock(stdout="10")  # 10 commits available
            elif "log" in cmd:
                return Mock(stdout="abc123|Fix bug 1")
            else:
                raise GitError("Unexpected command")

        mock_run_git.side_effect = side_effect
        mock_get_files.return_value = {"file1.py"}

        commits = self.git_tidy.get_commits_to_rebase()

        assert len(commits) == 1
        # Should have called with HEAD~9 range (10 commits, so HEAD~9)
        expected_range = "HEAD~9..HEAD"
        mock_run_git.assert_any_call(
            ["log", expected_range, "--pretty=format:%H|%s", "--reverse"]
        )

    def test_get_commits_to_rebase_empty(self):
        """Test getting commits when no commits found."""
        with patch.object(self.git_tidy, "run_git") as mock_run_git:
            mock_run_git.side_effect = [
                Mock(stdout="feature"),  # branch --show-current
                Mock(stdout="base123"),  # merge-base
                Mock(stdout="head456"),  # rev-parse HEAD
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
            Mock(),  # reset --hard base
            # Multi-file commit abc123 -> peel file1.py then file2.py
            Mock(),  # cherry-pick --no-commit abc123
            Mock(),  # reset HEAD (peel file1.py, not last)
            Mock(),  # add file1.py
            Mock(),  # stash push --keep-index --include-untracked
            Mock(),  # commit file1.py
            Mock(returncode=0),  # stash pop (check_output=False)
            Mock(),  # reset HEAD (peel file2.py, last)
            Mock(),  # add file2.py
            Mock(),  # commit file2.py
            # Single-file commit def456 -> plain cherry-pick
            Mock(),  # cherry-pick def456
        ]

        with patch("builtins.print") as mock_print:
            result = self.git_tidy.perform_split_rebase(commits)

        assert result is True
        mock_input.assert_called_once_with("\nProceed with split rebase? (y/N): ")

        # Verify git operations were called
        assert mock_run_git.call_count == 12  # All expected calls
        mock_run_git.assert_any_call(["rev-parse", "abc123^"])
        mock_run_git.assert_any_call(["reset", "--hard", "base123"])
        mock_run_git.assert_any_call(["cherry-pick", "--no-commit", "abc123"])
        mock_run_git.assert_any_call(["cherry-pick", "def456"])

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
    def test_rebase_skip_merged_dry_run(self, mock_run_git):
        """Test rebase_skip_merged dry-run prints unique commits."""
        # branch --show-current
        # fetch --all --prune (ignored)
        # cherry -v base branch -> + lines
        mock_run_git.side_effect = [
            Mock(stdout="feature/B"),  # current branch
            Mock(),  # fetch
            Mock(
                stdout="+ abc123 Commit A\n- def456 Commit elsewhere\n+ ghi789 Commit B"
            ),  # cherry
        ]

        with patch("builtins.print") as mock_print:
            self.git_tidy.rebase_skip_merged(
                {"base": "origin/main", "branch": None, "dry_run": True}
            )

        mock_print.assert_any_call(
            "Found 2 commits unique to feature/B relative to origin/main"
        )
        mock_print.assert_any_call("Would replay (oldest to newest):")

    @patch.object(GitTidy, "run_git")
    def test_rebase_skip_merged_exec_success(self, mock_run_git):
        """Test successful execution of rebase_skip_merged."""
        # current branch, fetch, cherry list, rev-parse HEAD, branch backup,
        # switch temp, cherry-pick for each sha, branch -f, switch back, branch -D
        mock_run_git.side_effect = [
            Mock(stdout="feature/B"),  # current branch
            Mock(),  # fetch
            Mock(stdout="+ abc123 A\n+ ghi789 B"),  # cherry
            Mock(stdout="deadbeefdeadbeef"),  # rev-parse HEAD
            Mock(),  # branch backup
            Mock(),  # switch -c temp from base
            Mock(returncode=0),  # cherry-pick abc123
            Mock(returncode=0),  # cherry-pick ghi789
            Mock(),  # branch -f
            Mock(),  # switch branch
            Mock(),  # branch -D temp
        ]

        with patch("builtins.print") as mock_print:
            # Disable prompt and enable backup
            self.git_tidy.rebase_skip_merged(
                {
                    "base": "origin/main",
                    "branch": None,
                    "dry_run": False,
                    "prompt": False,
                    "backup": True,
                }
            )

        mock_print.assert_any_call("Rebase-skip-merged completed successfully.")

    @patch.object(GitTidy, "run_git")
    def test_rebase_skip_merged_optimize_merge_and_bias(self, mock_run_git):
        """Test that optimize-merge sets -c prefixes and conflict bias adds -X arg."""
        mock_run_git.side_effect = [
            Mock(stdout="feature/B"),  # current branch
            Mock(),  # fetch
            Mock(stdout="+ abc123 A"),  # cherry
            Mock(stdout="deadbeefdeadbeef"),  # rev-parse
            Mock(),  # branch backup
            Mock(),  # switch -c temp
            Mock(returncode=0),  # cherry-pick with -X theirs
            Mock(),  # branch -f
            Mock(),  # switch branch
            Mock(),  # branch -D temp
        ]

        self.git_tidy.rebase_skip_merged(
            {
                "base": "origin/main",
                "dry_run": False,
                "prompt": False,
                "backup": True,
                "optimize_merge": True,
                "conflict_bias": "theirs",
            }
        )

        # Ensure at least one call included cherry-pick with -X theirs
        found = False
        for call in mock_run_git.call_args_list:
            args = call[0][0]
            if "cherry-pick" in args and "-X" in args and "theirs" in args:
                found = True
                break
        assert found

    @patch.object(GitTidy, "run_git")
    def test_rebase_skip_merged_chunk_and_max_conflicts(self, mock_run_git):
        """Test chunked replay and stopping on max conflicts."""
        mock_run_git.side_effect = [
            Mock(stdout="feature/B"),  # current branch
            Mock(),  # fetch
            Mock(stdout="+ a1 A\n+ a2 B\n+ a3 C"),  # cherry -> 3 commits
            Mock(stdout="deadbeefdeadbeef"),  # rev-parse
            Mock(),  # branch backup
            Mock(),  # switch -c temp
            Mock(returncode=1, stderr="conflict"),  # pick a1 -> fail
            Mock(),  # cherry-pick --abort
            Mock(),  # switch back
            Mock(),  # branch -D temp
        ]

        with patch("builtins.print") as mock_print:
            self.git_tidy.rebase_skip_merged(
                {
                    "base": "origin/main",
                    "prompt": False,
                    "backup": True,
                    "chunk_size": 1,
                    "max_conflicts": 1,
                }
            )

        mock_print.assert_any_call("Max conflicts reached; aborting")

    @patch.object(GitTidy, "run_git")
    def test_rebase_skip_merged_rerere_cache_import_export(
        self, mock_run_git, tmp_path
    ):
        """Test rerere cache import/export paths don't crash and attempt copy."""
        # Prepare a fake rerere cache directory
        src_cache = tmp_path / "rr"
        (src_cache / "sub").mkdir(parents=True)
        f = src_cache / "sub" / "file"
        f.write_text("data")

        mock_run_git.side_effect = [
            Mock(stdout="feature/B"),  # current
            Mock(),  # fetch
            Mock(stdout=""),  # cherry -> no unique
        ]

        # Dry run exits early
        self.git_tidy.rebase_skip_merged(
            {
                "base": "origin/main",
                "dry_run": True,
                "use_rerere_cache": True,
                "rerere_cache": str(src_cache),
            }
        )

        # Now run with import/export through the path where there are no commits
        mock_run_git.side_effect = [
            Mock(stdout="feature/B"),  # current
            Mock(),  # fetch
            Mock(stdout=""),  # cherry -> no unique
        ]
        with patch("builtins.print"):
            self.git_tidy.rebase_skip_merged(
                {
                    "base": "origin/main",
                    "dry_run": False,
                    "prompt": False,
                    "backup": False,
                    "use_rerere_cache": True,
                    "rerere_cache": str(src_cache),
                }
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
        mock_perform.assert_called_once_with(mock_commits, no_prompt=False)
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
        mock_perform.assert_called_once_with(mock_commits, no_prompt=False)
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

    @patch.object(GitTidy, "run_git")
    def test_preflight_check_clean(self, mock_run_git):
        # fetch, status clean, head subject, ahead count
        mock_run_git.side_effect = [
            Mock(stdout="feature/B"),  # show-current
            Mock(),  # fetch
            Mock(stdout=""),  # status clean
            Mock(stdout="feat: ok"),  # head subject
            Mock(stdout="1\t2"),  # ahead/behind
        ]
        with patch("builtins.print") as mock_print:
            self.git_tidy.preflight_check(
                {"allow_dirty": True, "allow_wip": False, "dry_run": True}
            )
        mock_print.assert_any_call("Preflight OK. Behind/ahead (base...branch): 1\t2")

    @patch.object(GitTidy, "run_git")
    def test_select_base_prefers_first_available(self, mock_run_git):
        # merge-base for first preferred succeeds
        mock_run_git.return_value = Mock(stdout="base123")
        base = self.git_tidy.select_base(
            {"preferred": ["origin/main", "master"], "fallback": "HEAD~5"}
        )
        assert base == "origin/main"

    @patch.object(GitTidy, "run_git")
    def test_auto_continue_nothing(self, mock_run_git):
        mock_run_git.side_effect = [Mock(returncode=1), Mock(returncode=1)]
        with patch("builtins.print") as mock_print:
            self.git_tidy.auto_continue()
        mock_print.assert_any_call("Nothing to continue")

    @patch.object(GitTidy, "run_git")
    def test_chunked_replay_missing_args(self, mock_run_git):
        with patch("builtins.print") as mock_print:
            self.git_tidy.chunked_replay({"base": None, "commits": [], "chunk_size": 0})
        mock_print.assert_any_call("Missing required arguments for chunked-replay")

    @patch.object(GitTidy, "run_git")
    def test_range_diff_report(self, mock_run_git):
        mock_run_git.return_value = Mock(returncode=0, stdout="diff ok")
        with patch("builtins.print") as mock_print:
            self.git_tidy.range_diff_report("A", "B")
        mock_print.assert_any_call("diff ok")

    def test_rerere_share_missing(self):
        with patch("builtins.print") as mock_print:
            self.git_tidy.rerere_share({})
        mock_print.assert_any_call("Missing action or path")

    @patch.object(GitTidy, "run_git")
    def test_smart_merge_preview_clean(self, mock_run_git):
        # switch target, merge --no-commit success, merge --abort
        mock_run_git.side_effect = [
            Mock(),  # switch target
            Mock(returncode=0),  # merge --no-commit clean
            Mock(),  # merge --abort
        ]
        with patch("builtins.print") as mock_print:
            self.git_tidy.smart_merge(
                {
                    "branch": "feature/X",
                    "into": "main",
                    "apply": False,
                    "prompt": False,
                    "backup": False,
                    "optimize_merge": False,
                    "rename_detect": True,
                }
            )
        mock_print.assert_any_call("Merge would be clean")

    @patch.object(GitTidy, "run_git")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "cleanup_backup")
    def test_smart_merge_apply_clean(self, mock_cleanup, mock_backup, mock_run_git):
        # switch, merge clean
        mock_run_git.side_effect = [
            Mock(),  # switch target
            Mock(returncode=0),  # merge clean
        ]
        with patch("builtins.print"):
            self.git_tidy.smart_merge(
                {
                    "branch": "feature/X",
                    "into": "main",
                    "apply": True,
                    "prompt": False,
                    "backup": True,
                    "optimize_merge": True,
                    "rename_detect": True,
                }
            )
        mock_backup.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch.object(GitTidy, "run_git")
    def test_smart_revert_preview_clean(self, mock_run_git):
        # select commits, revert --no-commit clean, revert --abort
        mock_run_git.side_effect = [
            Mock(stdout="a1\na2"),  # log -> selected SHAs
            Mock(returncode=0),  # revert a1 --no-commit
            Mock(returncode=0),  # revert a2 --no-commit
            Mock(),  # revert --abort
        ]
        with patch("builtins.print") as mock_print:
            self.git_tidy.smart_revert(
                {
                    "commits": [],
                    "range": "main..HEAD",
                    "count": None,
                    "apply": False,
                    "prompt": False,
                    "backup": False,
                    "optimize_merge": False,
                    "rename_detect": True,
                }
            )
        mock_print.assert_any_call("Revert would be clean")

    @patch.object(GitTidy, "run_git")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "cleanup_backup")
    def test_smart_revert_apply_commits(self, mock_cleanup, mock_backup, mock_run_git):
        # direct commits provided, revert clean then commit
        mock_run_git.side_effect = [
            Mock(returncode=0),  # revert a1
            Mock(returncode=0),  # revert a2
            Mock(returncode=0),  # commit --no-edit
        ]
        with patch("builtins.print"):
            self.git_tidy.smart_revert(
                {
                    "commits": ["a1", "a2"],
                    "apply": True,
                    "prompt": False,
                    "backup": True,
                    "optimize_merge": True,
                    "rename_detect": True,
                }
            )
        mock_backup.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch.object(GitTidy, "run_git")
    @patch.object(GitTidy, "select_base")
    @patch.object(GitTidy, "preflight_check")
    @patch.object(GitTidy, "rebase_skip_merged")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "cleanup_backup")
    def test_smart_rebase_dry_run(
        self,
        mock_cleanup,
        mock_backup,
        mock_rsm,
        mock_preflight,
        mock_select,
        mock_run_git,
    ):
        mock_select.return_value = "origin/main"
        with patch("builtins.print"):
            self.git_tidy.smart_rebase(
                {
                    "branch": "feature/B",
                    "base": None,
                    "dry_run": True,
                    "prompt": False,
                    "backup": False,
                }
            )
        mock_preflight.assert_called_once()
        mock_rsm.assert_not_called()
        mock_cleanup.assert_not_called()
        mock_backup.assert_not_called()

    @patch.object(GitTidy, "run_git")
    @patch.object(GitTidy, "select_base")
    @patch.object(GitTidy, "preflight_check")
    @patch.object(GitTidy, "rebase_skip_merged")
    @patch.object(GitTidy, "create_backup")
    @patch.object(GitTidy, "cleanup_backup")
    def test_smart_rebase_flag_combinations(
        self,
        mock_cleanup,
        mock_backup,
        mock_rsm,
        mock_preflight,
        mock_select,
        mock_run_git,
    ):
        mock_select.return_value = "origin/main"
        mock_run_git.return_value = Mock(returncode=0)

        # Define representative combinations
        prompt_opts = [True, False]
        backup_opts = [True, False]
        optimize_opts = [True, False]
        bias_opts = ["none", "ours", "theirs"]
        rename_opts = [True, False]
        skip_merged_opts = [True, False]

        combos = (
            (p, b, o, c, r, s)
            for p in prompt_opts
            for b in backup_opts
            for o in optimize_opts
            for c in bias_opts
            for r in rename_opts
            for s in skip_merged_opts
        )

        for prompt, backup, optimize, bias, rename, skip in combos:
            mock_preflight.reset_mock()
            mock_rsm.reset_mock()
            mock_backup.reset_mock()
            mock_cleanup.reset_mock()

            self.git_tidy.smart_rebase(
                {
                    "branch": "feature/B",
                    "base": None,
                    "dry_run": False,
                    "prompt": prompt,
                    "backup": backup,
                    "optimize_merge": optimize,
                    "conflict_bias": bias,
                    "rename_detect": rename,
                    "skip_merged": skip,
                }
            )

            # Preflight should always run
            assert mock_preflight.called
            if backup:
                assert mock_backup.called
                assert mock_cleanup.called
            else:
                assert not mock_backup.called
            # If skip_merged is False, smart_rebase will do a plain git rebase
            # which we don't mock here; only assert that in the skip=true case we called rebase_skip_merged
            if skip:
                assert mock_rsm.called


# ---------------------------------------------------------------------------
# Edge-case tests for ``GitTidy.split_commits`` against real fixture repos.
#
# These complement the system test in ``tests/system/test_split_commits.py``
# by covering surfaces that are awkward to express as a system run:
#
#   * failure rollback mid-split (injected via monkeypatch)
#   * empty commit range (``--base`` == HEAD)
#   * single-file-only range (no ``split off`` prefix should be applied)
#
# Fixtures are built with :class:`RepositoryBuilder` from
# ``tests.test_repository_fixtures`` for deterministic author/committer
# signatures and pinned commit content.
# ---------------------------------------------------------------------------


def _build_three_single_file_repo(base_path: Path) -> tuple[Path, str]:
    """Build a repo with three commits each touching exactly one (different) file.

    Returns the repo path and the SHA of the base (initial) commit, intended
    to be passed as ``--base`` to ``split-commits``.
    """
    repo_path = base_path / "repo_three_single_file"
    builder = RepositoryBuilder(repo_path)

    base_oid = builder.add_and_commit({"base.txt": "base\n"}, "Base: initial")
    builder.add_and_commit({"alpha.py": "# alpha\n"}, "S1: add alpha")
    builder.add_and_commit({"beta.py": "# beta\n"}, "S2: add beta")
    builder.add_and_commit({"gamma.py": "# gamma\n"}, "S3: add gamma")

    return repo_path, str(base_oid)


def _build_two_multi_file_repo(base_path: Path) -> tuple[Path, str]:
    """Build a repo with one base commit and one multi-file commit on top.

    Returns the repo path and the SHA of the base commit.
    """
    repo_path = base_path / "repo_two_multi_file"
    builder = RepositoryBuilder(repo_path)

    base_oid = builder.add_and_commit({"base.txt": "base\n"}, "Base: initial")
    builder.add_and_commit(
        {"x.py": "# x\n", "y.py": "# y\n", "z.py": "# z\n"},
        "M: add three files in one commit",
    )

    return repo_path, str(base_oid)


def _list_backup_branches(repo_path: Path) -> list[str]:
    """Return ``backup-*`` branches in the given repo via ``git branch --list``."""
    result = subprocess.run(
        ["git", "branch", "--list", "backup-*"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_path),
    )
    # ``git branch --list`` prefixes with two spaces (or ``* `` for current).
    return [
        line.lstrip("* ").strip() for line in result.stdout.splitlines() if line.strip()
    ]


def _current_head_sha(repo_path: Path) -> str:
    """Return the SHA of HEAD in ``repo_path``."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_path),
    )
    return result.stdout.strip()


def _commit_subjects(repo_path: Path, base_sha: str) -> list[str]:
    """Return the subjects of commits in ``base_sha..HEAD`` (oldest first)."""
    result = subprocess.run(
        ["git", "log", f"{base_sha}..HEAD", "--pretty=format:%s", "--reverse"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_path),
    )
    return [line for line in result.stdout.splitlines() if line]


def _commit_messages(repo_path: Path, base_sha: str) -> list[str]:
    """Return full commit messages in ``base_sha..HEAD`` (oldest first).

    Uses NUL byte separators so messages with embedded blank lines are parsed
    unambiguously.
    """
    result = subprocess.run(
        ["git", "log", f"{base_sha}..HEAD", "--pretty=format:%B%x00", "--reverse"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_path),
    )
    # Split on NUL; strip the trailing newline git adds before each NUL.
    return [chunk.strip("\n") for chunk in result.stdout.split("\x00") if chunk.strip()]


@pytest.fixture
def split_tmp_dir(tmp_path: Path) -> Path:
    """Pytest-managed temporary directory dedicated to fixture repos."""
    return tmp_path


def test_split_commits_failure_rollback(
    split_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mid-split failure must roll HEAD back to its original SHA.

    Strategy: build a real repo with one multi-file commit, then monkeypatch
    ``GitTidy.run_git`` so that the first ``cherry-pick`` invocation raises a
    :class:`GitError`. The wrapper in ``GitTidy.split_commits`` must catch the
    exception, restore HEAD via the backup branch, and call ``sys.exit(1)``.

    This documents the externally observable rollback contract from the user's
    perspective: HEAD is what it was before the command ran.

    Note on the backup branch: the project's current ``restore_from_backup``
    deletes the backup branch after restoring HEAD (see ``core.py:77``). The
    initiative spec aspirationally describes the backup as "preserved on
    failure", but the in-tree implementation removes it. The assertions below
    only cover the HEAD restoration, which is the contract that matters for
    not-losing-work; the backup-branch lifecycle discrepancy is documented in
    task 3's progress notes rather than enforced here.
    """
    repo_path, base_sha = _build_two_multi_file_repo(split_tmp_dir)
    original_head = _current_head_sha(repo_path)
    assert original_head != base_sha  # sanity: there's something to split

    monkeypatch.chdir(repo_path)

    git_tidy = GitTidy()
    real_run_git = git_tidy.run_git

    def failing_run_git(
        cmd: list[str],
        check_output: bool = True,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        # Inject a deterministic failure on the first cherry-pick attempt.
        # Earlier sub-calls (rev-parse, branch creation, status, reset --hard)
        # are allowed through so the backup branch genuinely exists at the
        # point of failure.
        if cmd and cmd[0] == "cherry-pick":
            raise GitError("Injected cherry-pick failure for rollback test")
        return real_run_git(cmd, check_output=check_output, env=env)

    monkeypatch.setattr(git_tidy, "run_git", failing_run_git)

    with pytest.raises(SystemExit) as exc_info:
        git_tidy.split_commits(base_ref=base_sha, no_prompt=True)

    assert exc_info.value.code == 1

    # HEAD must be restored to where it was before the command ran.
    assert _current_head_sha(repo_path) == original_head

    # The restore path also resets to ``original_head``; the on-disk tree
    # must therefore still contain the multi-file commit's files.
    for filename in ("x.py", "y.py", "z.py"):
        assert (
            repo_path / filename
        ).is_file(), f"expected {filename} to be restored after failure rollback"


def test_split_commits_empty_range(
    split_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--base`` equal to HEAD must early-return cleanly with no orphan backup.

    When the requested range contains zero commits, ``split_commits`` prints
    "No commits found to split" and returns. The wrapper still creates a
    backup at the start (via ``create_backup``) but cleans it up on the
    early-return path. Asserting the externally observable backup-branch list
    is empty afterwards locks that contract in.
    """
    repo_path, _ = _build_three_single_file_repo(split_tmp_dir)
    head_sha = _current_head_sha(repo_path)

    monkeypatch.chdir(repo_path)

    git_tidy = GitTidy()

    # Capture printed output to verify the early-return message.
    printed: list[str] = []

    def capture_print(*args: Any, **kwargs: Any) -> None:
        printed.append(" ".join(str(a) for a in args))

    monkeypatch.setattr("builtins.print", capture_print)

    # base_ref == HEAD means ``HEAD..HEAD``: zero commits.
    git_tidy.split_commits(base_ref=head_sha, no_prompt=True)

    assert any(
        "No commits found to split" in line for line in printed
    ), f"expected early-return message, got: {printed!r}"

    # No commits were created or destroyed.
    assert _current_head_sha(repo_path) == head_sha

    # No orphan backup branch remains. ``create_backup`` does run on the
    # empty-range path, so this asserts that ``cleanup_backup`` correctly
    # removed it on the way out.
    assert _list_backup_branches(repo_path) == []


def test_split_commits_single_file_only_range(
    split_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A range of single-file commits must pass through unchanged.

    Builds a fixture with three commits each touching exactly one (different)
    file. After ``split-commits``, all three commits must remain (count == 3,
    not 6) and each commit's message must be the original message verbatim --
    crucially, *no* ``split off`` prefix.
    """
    repo_path, base_sha = _build_three_single_file_repo(split_tmp_dir)
    original_subjects = _commit_subjects(repo_path, base_sha)
    assert original_subjects == ["S1: add alpha", "S2: add beta", "S3: add gamma"]

    monkeypatch.chdir(repo_path)

    git_tidy = GitTidy()
    git_tidy.split_commits(base_ref=base_sha, no_prompt=True)

    new_subjects = _commit_subjects(repo_path, base_sha)
    assert (
        new_subjects == original_subjects
    ), f"single-file commits should be preserved verbatim, got {new_subjects!r}"

    new_messages = _commit_messages(repo_path, base_sha)
    assert (
        len(new_messages) == 3
    ), f"expected exactly 3 commits (not 6), got {len(new_messages)}: {new_messages!r}"
    for message in new_messages:
        assert not message.startswith(
            "split off "
        ), f"single-file commit got an unexpected 'split off' prefix: {message!r}"

    # Successful split removes the backup branch on the way out.
    assert _list_backup_branches(repo_path) == []


# ---------------------------------------------------------------------------
# Unit tests for ``GitTidy._format_split_message``.
#
# These lock in the per-file commit message format produced by
# ``_emit_per_file_commits`` so the format change cannot regress silently.
# The helper is a pure string function, cheap to test in isolation.
# ---------------------------------------------------------------------------


def test_format_split_message_single_line_subject() -> None:
    """A subject-only message gets ``(split off <file>)`` appended."""
    result = GitTidy._format_split_message("feat: X", "a.py")
    assert result == "feat: X (split off a.py)"


def test_format_split_message_subject_and_body() -> None:
    """The body is preserved verbatim under the extended subject."""
    original = "feat: X\n\nLong body here."
    result = GitTidy._format_split_message(original, "a.py")
    assert result == "feat: X (split off a.py)\n\nLong body here."


def test_format_split_message_preserves_trailers() -> None:
    """Body, blank lines, and trailers must be byte-identical to the input."""
    original = (
        "feat: X\n"
        "\n"
        "Implements RFC 8259 string escaping. Closes #142.\n"
        "\n"
        "Signed-off-by: Alice <alice@example.com>"
    )
    result = GitTidy._format_split_message(original, "serializer.py")

    expected = (
        "feat: X (split off serializer.py)\n"
        "\n"
        "Implements RFC 8259 string escaping. Closes #142.\n"
        "\n"
        "Signed-off-by: Alice <alice@example.com>"
    )
    assert result == expected


def test_format_split_message_subject_with_parens() -> None:
    """Conventional-commit scope syntax is preserved at the start of the subject."""
    result = GitTidy._format_split_message("feat(api): X", "a.py")
    assert result == "feat(api): X (split off a.py)"


def test_format_split_message_trailing_newline_only() -> None:
    """A message ending in a newline yields a subject + empty body (newline preserved).

    ``str.partition('\\n')`` returns ``('feat: X', '\\n', '')`` for input
    ``"feat: X\\n"``. The non-empty separator means we take the
    ``f"{new_subject}\\n{rest}"`` branch with ``rest == ''``, producing
    ``"feat: X (split off a.py)\\n"``.
    """
    result = GitTidy._format_split_message("feat: X\n", "a.py")
    assert result == "feat: X (split off a.py)\n"


def test_format_split_message_filename_with_special_chars() -> None:
    """File names are passed through verbatim — git accepts arbitrary subjects."""
    result = GitTidy._format_split_message("fix: bug", "src/sub dir/file (copy).py")
    assert result == "fix: bug (split off src/sub dir/file (copy).py)"


# Suppress an unused-import complaint if pygit2 is not otherwise referenced
# in this module. ``RepositoryBuilder`` already uses pygit2, but the import
# above guarantees a clean failure mode if the dev dependency is missing.
_ = pygit2
