"""Tests for git-tidy CLI functionality."""

from unittest.mock import Mock, patch

import pytest

from git_tidy.cli import cmd_group_commits, create_parser, main
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

        # Test help output contains group-commits
        help_output = parser.format_help()
        assert "group-commits" in help_output

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

    def test_integration_help_output(self):
        """Integration test for help output."""
        parser = create_parser()

        # Test main help
        help_output = parser.format_help()
        assert "git-tidy" in help_output
        assert "group-commits" in help_output
        assert "Examples:" in help_output

    def test_integration_subcommand_help(self):
        """Integration test for subcommand help."""
        parser = create_parser()

        # Test that --help works (it will exit, so we catch that)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["group-commits", "--help"])
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
