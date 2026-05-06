"""System tests for git-tidy split-commits command."""

import tempfile
from pathlib import Path

import pygit2
import pytest

from tests.test_advanced_repository_fixtures import (
    AdvancedRepositoryBuilder,
    TestAdvancedRepositoryFixtures,
)
from tests.test_repository_fixtures import TestRepositoryFixtures

from .framework.git_tidy_runner import ExpectedOutcome, GitTidyRunner
from .framework.result_validator import RepositoryState, ResultValidator

# Filenames in the multi-file commit. Mirrors the user's reproducer (12 files,
# mixed extensions). Sorted alphabetically because ``perform_split_rebase``
# emits ``split off <file>`` commits in sorted order.
_MULTI_FILE_NAMES: list[str] = [
    "a.h",
    "b.h",
    "c.cpp",
    "d.cpp",
    "e.h",
    "f.cpp",
    "g.cpp",
    "h.cpp",
    "i.cpp",
    "j.cpp",
    "k.py",
    "l.cpp",
]

# First-line messages of the single-file follow-up commits. Order matches the
# order they are committed in the fixture (oldest first).
_SINGLE_FILE_COMMITS: list[tuple[str, str]] = [
    ("m.cpp", "S1: tweak m.cpp"),
    ("n.py", "S2: tweak n.py"),
    ("o.h", "S3: tweak o.h"),
]


def _build_multi_file_split_repo(base_path: Path) -> tuple[Path, str]:
    """Create the reproducer repository.

    Layout (oldest -> newest):
        base    : initial commit on ``main`` with a single ``base.txt`` file.
        multi   : one commit touching all 12 files in ``_MULTI_FILE_NAMES``.
        s1..s3  : three single-file follow-up commits (``_SINGLE_FILE_COMMITS``).

    Returns the repo path and the SHA of the ``base`` commit (intended to be
    passed to ``git-tidy split-commits --base <sha>``).
    """

    repo_path = base_path / "repo_multi_file_split"
    builder = AdvancedRepositoryBuilder(repo_path)

    # Base commit on main.
    base_sha = str(builder.add_and_commit({"base.txt": "base\n"}, "Base: initial"))

    # One multi-file commit.
    multi_files = {
        name: f"// initial content of {name}\n" for name in _MULTI_FILE_NAMES
    }
    builder.add_and_commit(multi_files, "M: introduce 12 files at once")

    # Three single-file follow-up commits.
    for filename, message in _SINGLE_FILE_COMMITS:
        builder.add_and_commit({filename: f"// {filename} edited\n"}, message)

    return repo_path, base_sha


class TestSplitCommitsSystem:
    """System tests for split-commits command."""

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
    def test_split_commits_split_targets_preview(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on split_targets repository in preview mode."""
        # Create repository with multi-file commits
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_split_targets(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits in dry-run mode
        result = runner.run_with_dry_run(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Validate preview mode - no changes should be made
        validator.validate_result(
            result, ExpectedOutcome.PREVIEW_ONLY, pre_state, post_state
        )

        # Should indicate changes would be made
        assert runner.has_changes_indicated(
            result
        ), "Expected preview to show changes would be made"

    @pytest.mark.fast
    def test_split_commits_split_targets_apply(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on split_targets repository with actual changes."""
        # Create repository with multi-file commits
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_split_targets(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits to apply changes
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Split operation may fail due to conflicts in some repositories
        if result.exit_code == 0:
            # If successful, validate execution with changes
            validator.validate_result(
                result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state
            )
            # Commit count should increase (splitting commits creates more commits)
            assert (
                post_state.commit_count > pre_state.commit_count
            ), "Expected more commits after splitting"
            # Backup branch should be cleaned up on success
            validator.validate_backup_created(repo_path, expected=False)
        else:
            # If failed, should restore gracefully
            validator.validate_result(
                result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state
            )
            # Should indicate conflicts or errors
            assert (
                "Error:" in result.stdout or "conflicts" in result.stdout.lower()
            ), "Expected error indication"

    @pytest.mark.fast
    def test_split_commits_merge_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on repository with merge commits."""
        # Create repository with merge commits
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_merge_commits(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed (may or may not have changes depending on commit structure)
        if runner.has_changes_indicated(result):
            validator.validate_result(
                result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state
            )
        else:
            validator.validate_result(
                result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state
            )

    @pytest.mark.fast
    def test_split_commits_with_base(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits with custom base commit."""
        # Create repository with split targets
        fixtures = TestAdvancedRepositoryFixtures()
        repo_path = fixtures.create_repo_split_targets(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits with base specification
        result = runner.run_and_apply(repo_path, "split-commits", ["--base", "HEAD~2"])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed or fail gracefully
        if result.exit_code == 0:
            if runner.has_changes_indicated(result):
                validator.validate_result(
                    result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state
                )
            else:
                validator.validate_result(
                    result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state
                )
        else:
            # If failed due to conflicts, should restore gracefully
            validator.validate_result(
                result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state
            )

    @pytest.mark.fast
    def test_split_commits_single_file_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on repository with single-file commits."""
        # Create repository where commits already touch single files
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_linear_simple(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should succeed but make no changes (already single-file commits)
        validator.validate_result(
            result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state
        )

    @pytest.mark.fast
    def test_split_commits_insufficient_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on repository with insufficient commits."""
        # Create repository with only one commit
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_single_commit(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should either succeed with no changes or fail gracefully
        if result.exit_code == 0:
            validator.validate_result(
                result, ExpectedOutcome.SUCCESS_NO_CHANGES, pre_state, post_state
            )
        else:
            validator.validate_result(
                result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state
            )

    @pytest.mark.fast
    def test_split_commits_multi_file_then_single_file_commits(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Reproduce the user-reported failure of split-commits.

        Repository shape (matches the user's reproducer):
          * 1 base commit on main
          * 1 multi-file commit touching 12 files
          * 3 single-file follow-up commits

        Expected (after the fix in task 2):
          * Total commits = base + 12 (split off files) + 3 (single-file as-is) = 16
          * Multi-file commit becomes 12 ``split off <file>`` commits, in
            alphabetical order, oldest first.
          * Single-file commits keep their original messages verbatim
            (no ``split off`` prefix).

        On the CURRENT (broken) implementation the run fails with
        ``error: Your local changes to the following files would be
        overwritten by merge`` because ``perform_split_rebase`` does
        ``git reset --soft <base>`` then ``git cherry-pick --no-commit
        <sha>`` against the still-modified working tree. This test is the
        regression artifact for that fix.
        """
        repo_path, base_sha = _build_multi_file_split_repo(temp_dir)

        # Sanity-check fixture shape.
        repo = pygit2.Repository(str(repo_path))
        assert len(list(repo.walk(repo.head.target))) == 1 + 1 + len(
            _SINGLE_FILE_COMMITS
        ), "Fixture should have exactly 5 commits"

        pre_state = RepositoryState(repo_path)

        result = runner.run_and_apply(repo_path, "split-commits", ["--base", base_sha])

        post_state = RepositoryState(repo_path)

        validator.validate_result(
            result, ExpectedOutcome.SUCCESS_WITH_CHANGES, pre_state, post_state
        )

        # Total commits = base + per-file (12) + single-file (3) = 16.
        expected_total = 1 + len(_MULTI_FILE_NAMES) + len(_SINGLE_FILE_COMMITS)
        validator.validate_commit_count(post_state, expected_total)

        # Backup branch should be cleaned up on success.
        validator.validate_backup_created(repo_path, expected=False)

        # Expected commit messages, oldest-first:
        #   Base: initial
        #   split off a.h  ... split off l.cpp     (alphabetical)
        #   S1: tweak m.cpp
        #   S2: tweak n.py
        #   S3: tweak o.h
        expected_first_lines = (
            ["Base: initial"]
            + [f"split off {name}" for name in sorted(_MULTI_FILE_NAMES)]
            + [message for _, message in _SINGLE_FILE_COMMITS]
        )
        validator.validate_commit_messages_match(
            post_state, expected_first_lines, order="oldest_first"
        )

    @pytest.mark.fast
    def test_split_commits_empty_repository(
        self, temp_dir: Path, runner: GitTidyRunner, validator: ResultValidator
    ) -> None:
        """Test split-commits on empty repository."""
        # Create empty repository
        fixtures = TestRepositoryFixtures()
        repo_path = fixtures.create_repo_no_commits(temp_dir)

        # Capture initial state
        pre_state = RepositoryState(repo_path)

        # Run split-commits
        result = runner.run_and_apply(repo_path, "split-commits", [])

        # Capture post state
        post_state = RepositoryState(repo_path)

        # Should fail gracefully on empty repository
        validator.validate_result(
            result, ExpectedOutcome.ERROR_GRACEFUL, pre_state, post_state
        )
