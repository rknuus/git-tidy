"""Tests for git-tidy CLI functionality."""

from unittest.mock import Mock, patch

import pytest

from git_tidy.cli import (
    cmd_group_commits,
    cmd_split_commits,
    cmd_squash_all,
    cmd_configure_repo,
    cmd_rebase_skip_merged,
    create_parser,
    main,
)
from git_tidy.core import GitTidy


class TestCLI:
    """Test class for CLI functionality."""

    def test_create_parser(self):
        """Test parser creation."""
        parser = create_parser()

        assert parser.prog == "git-tidy"
        assert "Tools for tidying up git commits" in parser.description

    def test_create_parser_subcommands(self):
        """Test that subcommands are properly created."""
        parser = create_parser()

        # Test help output contains all commands
        help_output = parser.format_help()
        assert "group-commits" in help_output
        assert "split-commits" in help_output
        assert "squash-all" in help_output
        assert "configure-repo" in help_output
        assert "rebase-skip-merged" in help_output

    def test_parse_group_commits_default(self):
        """Test parsing group-commits with default arguments."""
        parser = create_parser()
        args = parser.parse_args(["group-commits"])

        assert args.command == "group-commits"
        assert args.base is None
        assert args.threshold == 0.3
        assert args.dry_run is False

    def test_parse_group_commits_all_args(self):
        """Test parsing group-commits with all arguments."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "group-commits",
                "--base",
                "origin/main",
                "--threshold",
                "0.5",
                "--dry-run",
            ]
        )

        assert args.command == "group-commits"
        assert args.base == "origin/main"
        assert args.threshold == 0.5
        assert args.dry_run is True

    def test_parse_split_commits_default(self):
        """Test parsing split-commits with default arguments."""
        parser = create_parser()
        args = parser.parse_args(["split-commits"])

        assert args.command == "split-commits"
        assert args.base is None
        assert args.dry_run is False

    def test_parse_split_commits_all_args(self):
        """Test parsing split-commits with all arguments."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "split-commits",
                "--base",
                "origin/main",
                "--dry-run",
            ]
        )

        assert args.command == "split-commits"
        assert args.base == "origin/main"
        assert args.dry_run is True

    def test_parse_squash_all_default(self):
        """Test parsing squash-all with default arguments."""
        parser = create_parser()
        args = parser.parse_args(["squash-all"])

        assert args.command == "squash-all"
        assert args.base is None

    def test_parse_squash_all_with_base(self):
        """Test parsing squash-all with base argument."""
        parser = create_parser()
        args = parser.parse_args(["squash-all", "--base", "origin/main"])

        assert args.command == "squash-all"
        assert args.base == "origin/main"

    def test_parse_version(self):
        """Test version argument."""
        parser = create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])

        assert exc_info.value.code == 0

    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "group_commits")
    def test_cmd_group_commits_dry_run(self, mock_group, mock_get_commits):
        """Test group-commits command in dry-run mode."""
        # Setup mocks
        mock_commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
            {"sha": "def456", "subject": "Fix bug 2", "files": {"file2.py"}},
        ]
        mock_groups = [
            [mock_commits[0]],
            [mock_commits[1]],
        ]
        mock_get_commits.return_value = mock_commits
        mock_group.return_value = mock_groups

        args = Mock()
        args.dry_run = True
        args.base = None
        args.threshold = 0.3

        with patch("builtins.print") as mock_print:
            with patch.object(GitTidy, "describe_group") as mock_describe:
                mock_describe.side_effect = ["Files: file1.py", "Files: file2.py"]
                cmd_group_commits(args)

        # Verify the right methods were called
        mock_get_commits.assert_called_once_with(None)
        mock_group.assert_called_once_with(mock_commits, 0.3)

        # Verify output
        mock_print.assert_any_call("Found 2 commits, would group into 2 groups:")

    @patch.object(GitTidy, "run")
    def test_cmd_group_commits_execute(self, mock_run):
        """Test group-commits command execution (not dry-run)."""
        args = Mock()
        args.dry_run = False
        args.base = "origin/main"
        args.threshold = 0.5

        cmd_group_commits(args)

        mock_run.assert_called_once_with("origin/main", 0.5)

    @patch.object(GitTidy, "get_commits_to_rebase")
    def test_cmd_split_commits_dry_run(self, mock_get_commits):
        """Test split-commits command in dry-run mode."""
        # Setup mocks
        mock_commits = [
            {
                "sha": "abc123",
                "subject": "Fix bug 1",
                "files": {"file1.py", "file2.py"},
            },
            {"sha": "def456", "subject": "Fix bug 2", "files": {"file3.py"}},
        ]
        mock_get_commits.return_value = mock_commits

        args = Mock()
        args.dry_run = True
        args.base = None

        with patch("builtins.print") as mock_print:
            cmd_split_commits(args)

        # Verify the right methods were called
        mock_get_commits.assert_called_once_with(None)

        # Verify output
        mock_print.assert_any_call("Found 2 commits to split:")
        mock_print.assert_any_call("\nCommit abc123: Fix bug 1")
        mock_print.assert_any_call("  Files (2): file1.py, file2.py")
        mock_print.assert_any_call("  Would create 2 separate commits:")
        mock_print.assert_any_call("    - split off file1.py")
        mock_print.assert_any_call("    - split off file2.py")

    @patch.object(GitTidy, "split_commits")
    def test_cmd_split_commits_execute(self, mock_split):
        """Test split-commits command execution (not dry-run)."""
        args = Mock()
        args.dry_run = False
        args.base = "origin/main"

        cmd_split_commits(args)

        mock_split.assert_called_once_with("origin/main")

    @patch.object(GitTidy, "get_commits_to_rebase")
    def test_cmd_split_commits_empty_commits(self, mock_get_commits):
        """Test split-commits with no commits found."""
        mock_get_commits.return_value = []

        args = Mock()
        args.dry_run = True
        args.base = "HEAD~5"

        with patch("builtins.print") as mock_print:
            cmd_split_commits(args)

        mock_print.assert_any_call("Found 0 commits to split:")

    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "run_git")
    def test_cmd_squash_all_success(self, mock_run_git, mock_get_commits):
        """Test squash-all command with commits found."""
        mock_commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
            {"sha": "def456", "subject": "Fix bug 2", "files": {"file2.py"}},
        ]
        mock_get_commits.return_value = mock_commits
        mock_run_git.return_value = Mock(stdout="base789")

        args = Mock()
        args.base = "HEAD~5"

        with patch("builtins.print") as mock_print:
            cmd_squash_all(args)

        # Verify the right methods were called
        mock_get_commits.assert_called_once_with("HEAD~5")
        mock_run_git.assert_called_once_with(["rev-parse", "abc123^"])

        # Verify output
        mock_print.assert_any_call("Found 2 commits to squash:")
        mock_print.assert_any_call("  abc123 Fix bug 1")
        mock_print.assert_any_call("  def456 Fix bug 2")
        mock_print.assert_any_call(
            "\nTo squash all commits into one, run these commands:"
        )
        mock_print.assert_any_call("  git reset --soft base789")
        mock_print.assert_any_call('  git commit -m "Your new commit message"')
        mock_print.assert_any_call("\nThis will:")
        mock_print.assert_any_call(
            "  - Reset to commit base789 (keeping all changes staged)"
        )
        mock_print.assert_any_call(
            "  - Allow you to create a single commit with all changes"
        )
        mock_print.assert_any_call("  - Combine 2 commits into 1 commit")

    @patch.object(GitTidy, "get_commits_to_rebase")
    def test_cmd_squash_all_no_commits(self, mock_get_commits):
        """Test squash-all command with no commits found."""
        mock_get_commits.return_value = []

        args = Mock()
        args.base = None

        with patch("builtins.print") as mock_print:
            cmd_squash_all(args)

        mock_get_commits.assert_called_once_with(None)
        mock_print.assert_called_once_with("No commits found to squash")

    @patch("git_tidy.cli.create_parser")
    def test_main_no_subcommand(self, mock_create_parser):
        """Test main function when no subcommand is provided."""
        mock_parser = Mock()
        mock_parser.parse_args.return_value = Mock(spec=[])  # No 'func' attribute
        mock_create_parser.return_value = mock_parser

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        mock_parser.print_help.assert_called_once()

    @patch("git_tidy.cli.create_parser")
    def test_main_with_subcommand(self, mock_create_parser):
        """Test main function with valid subcommand."""
        mock_func = Mock()
        mock_args = Mock()
        mock_args.func = mock_func

        mock_parser = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        main()

        mock_func.assert_called_once_with(mock_args)

    def test_parse_configure_repo_defaults(self):
        """Test parsing configure-repo with defaults."""
        parser = create_parser()
        args = parser.parse_args(["configure-repo"])

        assert args.command == "configure-repo"
        assert args.scope == "local"
        assert args.preset == "safe"
        assert args.enable is None
        assert args.disable is None
        assert args.lockfile_policy is None
        assert args.dry_run is False
        assert args.no_prompt is False
        assert args.backup_path is None
        assert args.undo is False

    @patch.object(GitTidy, "configure_repo")
    def test_cmd_configure_repo_dispatch(self, mock_configure):
        """Test dispatch of configure-repo to core with options."""
        args = Mock()
        args.scope = "global"
        args.preset = "safe"
        args.enable = ["rerere", "zdiff3"]
        args.disable = ["drivers"]
        args.lockfile_policy = "none"
        args.dry_run = True
        args.no_prompt = True
        args.backup_path = ".git-tidy/configure-repo.bak"
        args.undo = False

        cmd_configure_repo(args)

        mock_configure.assert_called_once()

    def test_parse_rebase_skip_merged_defaults(self):
        """Test parsing rebase-skip-merged with defaults."""
        parser = create_parser()
        args = parser.parse_args(["rebase-skip-merged"])

        assert args.command == "rebase-skip-merged"
        assert args.base is None
        assert args.branch is None
        assert args.dry_run is False
        assert args.prompt is True
        assert args.backup is True
        assert args.by_groups is False
        assert args.optimize_merge is False
        assert args.conflict_bias == "none"
        assert args.use_rerere_cache is False
        assert args.auto_resolve_trivial is False
        assert args.rename_detect is True
        assert args.lint is False
        assert args.test is False
        assert args.build is False
        assert args.report == "text"
        assert args.summary is True

    @patch.object(GitTidy, "rebase_skip_merged")
    def test_cmd_rebase_skip_merged_dispatch(self, mock_rsm):
        """Test dispatch of rebase-skip-merged to core with options."""
        args = Mock()
        args.base = "origin/main"
        args.branch = "feature/B"
        args.dry_run = True
        args.prompt = False
        args.backup = False
        args.resume_from = None
        args.chunk_size = None
        args.by_groups = False
        args.max_conflicts = None
        args.optimize_merge = True
        args.conflict_bias = "theirs"
        args.rerere_cache = None
        args.use_rerere_cache = False
        args.auto_resolve_trivial = True
        args.rename_detect = True
        args.lint = False
        args.test = False
        args.build = False
        args.report = "text"
        args.summary = True

        cmd_rebase_skip_merged(args)

        mock_rsm.assert_called_once()

    def test_integration_help_output(self):
        """Integration test for help output."""
        parser = create_parser()

        # Test main help
        help_output = parser.format_help()
        assert "git-tidy" in help_output
        assert "group-commits" in help_output
        assert "split-commits" in help_output
        assert "squash-all" in help_output
        assert "Examples:" in help_output

    def test_integration_subcommand_help(self):
        """Integration test for subcommand help."""
        parser = create_parser()

        # Test that --help works (it will exit, so we catch that)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["group-commits", "--help"])
        assert exc_info.value.code == 0

        # Test split-commits help
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["split-commits", "--help"])
        assert exc_info.value.code == 0

        # Test squash-all help
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["squash-all", "--help"])
        assert exc_info.value.code == 0

        # Test new helper commands help
        for cmd in [
            "preflight-check",
            "select-base",
            "auto-continue",
            "auto-resolve-trivial",
            "chunked-replay",
            "range-diff-report",
            "validate",
            "rerere-share",
            "checkpoint-create",
            "checkpoint-restore",
        ]:
            with pytest.raises(SystemExit) as exc_info:
                parser.parse_args([cmd, "--help"])
            assert exc_info.value.code == 0

    @patch("sys.argv", ["git-tidy"])
    @patch("git_tidy.cli.create_parser")
    def test_main_integration_no_args(self, mock_create_parser):
        """Integration test for main with no arguments."""
        mock_parser = Mock()
        mock_parser.parse_args.return_value = Mock(spec=[])
        mock_create_parser.return_value = mock_parser

        with pytest.raises(SystemExit):
            main()

        mock_parser.print_help.assert_called_once()


class TestCLIEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_threshold_range(self):
        """Test handling of invalid threshold values."""
        parser = create_parser()

        # These would be caught by argparse type checking
        with pytest.raises(SystemExit):
            parser.parse_args(["group-commits", "--threshold", "invalid"])

    @patch.object(GitTidy, "get_commits_to_rebase")
    def test_cmd_group_commits_empty_commits(self, mock_get_commits):
        """Test group-commits with no commits found."""
        mock_get_commits.return_value = []

        args = Mock()
        args.dry_run = True
        args.base = None
        args.threshold = 0.3

        with patch("builtins.print") as mock_print:
            cmd_group_commits(args)

        mock_print.assert_any_call("Found 0 commits, would group into 0 groups:")

    @patch.object(GitTidy, "get_commits_to_rebase")
    @patch.object(GitTidy, "group_commits")
    def test_cmd_group_commits_single_group(self, mock_group, mock_get_commits):
        """Test group-commits with single group output."""
        mock_commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
        ]
        mock_groups = [mock_commits]
        mock_get_commits.return_value = mock_commits
        mock_group.return_value = mock_groups

        args = Mock()
        args.dry_run = True
        args.base = "HEAD~5"
        args.threshold = 0.1

        with patch("builtins.print") as mock_print:
            with patch.object(GitTidy, "describe_group") as mock_describe:
                mock_describe.return_value = "Files: file1.py"
                cmd_group_commits(args)

        mock_get_commits.assert_called_once_with("HEAD~5")
        mock_group.assert_called_once_with(mock_commits, 0.1)
        mock_print.assert_any_call("Found 1 commits, would group into 1 groups:")

    @patch.object(GitTidy, "get_commits_to_rebase")
    def test_cmd_split_commits_single_file_commits(self, mock_get_commits):
        """Test split-commits with commits that already have single files."""
        mock_commits = [
            {"sha": "abc123", "subject": "Fix bug 1", "files": {"file1.py"}},
            {"sha": "def456", "subject": "Fix bug 2", "files": {"file2.py"}},
        ]
        mock_get_commits.return_value = mock_commits

        args = Mock()
        args.dry_run = True
        args.base = None

        with patch("builtins.print") as mock_print:
            cmd_split_commits(args)

        # Should show that each commit would create 1 separate commit
        mock_print.assert_any_call("Found 2 commits to split:")
        mock_print.assert_any_call("  Would create 1 separate commits:")
        mock_print.assert_any_call("    - split off file1.py")
        mock_print.assert_any_call("    - split off file2.py")

    @patch.object(GitTidy, "get_commits_to_rebase")
    def test_cmd_split_commits_mixed_file_counts(self, mock_get_commits):
        """Test split-commits with mixed file counts."""
        mock_commits = [
            {"sha": "abc123", "subject": "Single file", "files": {"file1.py"}},
            {
                "sha": "def456",
                "subject": "Multiple files",
                "files": {"file2.py", "file3.py", "file4.py"},
            },
            {"sha": "ghi789", "subject": "Empty commit", "files": set()},
        ]
        mock_get_commits.return_value = mock_commits

        args = Mock()
        args.dry_run = True
        args.base = None

        with patch("builtins.print") as mock_print:
            cmd_split_commits(args)

        # Should show different handling for each type
        mock_print.assert_any_call("Found 3 commits to split:")
        mock_print.assert_any_call("\nCommit abc123: Single file")
        mock_print.assert_any_call("  Files (1): file1.py")
        mock_print.assert_any_call("  Would create 1 separate commits:")
        mock_print.assert_any_call("    - split off file1.py")

        mock_print.assert_any_call("\nCommit def456: Multiple files")
        mock_print.assert_any_call("  Files (3): file2.py, file3.py, file4.py")
        mock_print.assert_any_call("  Would create 3 separate commits:")
        mock_print.assert_any_call("    - split off file2.py")
        mock_print.assert_any_call("    - split off file3.py")
        mock_print.assert_any_call("    - split off file4.py")

        mock_print.assert_any_call("\nCommit ghi789: Empty commit")
        mock_print.assert_any_call("  Files (0): ")
        mock_print.assert_any_call("  Would create 0 separate commits:")
