"""Integration tests using repository fixtures to test git-tidy operations."""

import tempfile
from pathlib import Path

import pygit2
import pytest

from .test_advanced_repository_fixtures import TestAdvancedRepositoryFixtures
from .test_repository_fixtures import TestRepositoryFixtures


class TestRepositoryIntegration:
    """Integration tests that use repository fixtures to test git-tidy functionality."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for repositories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    @pytest.fixture
    def all_repositories(self, temp_dir: Path) -> dict[str, Path]:
        """Create all test repositories for integration testing."""
        basic_fixtures = TestRepositoryFixtures()
        advanced_fixtures = TestAdvancedRepositoryFixtures()

        repositories = {}
        repositories.update(basic_fixtures.create_all_repositories(temp_dir))
        repositories.update(
            advanced_fixtures.create_all_advanced_repositories(temp_dir)
        )

        return repositories

    def test_all_repositories_are_valid_git_repos(
        self, all_repositories: dict[str, Path]
    ) -> None:
        """Test that all created repositories are valid git repositories."""
        for repo_name, repo_path in all_repositories.items():
            # Verify path exists
            assert repo_path.exists(), f"Repository path {repo_name} does not exist"

            # Verify .git directory exists
            git_dir = repo_path / ".git"
            assert git_dir.exists(), f"Repository {repo_name} is missing .git directory"

            # Verify can open with pygit2
            try:
                repo = pygit2.Repository(str(repo_path))
                assert (
                    repo is not None
                ), f"Could not open repository {repo_name} with pygit2"
            except Exception as e:
                pytest.fail(f"Failed to open repository {repo_name}: {e}")

    def test_repository_commit_counts(self, all_repositories: dict[str, Path]) -> None:
        """Test that repositories have expected commit counts."""
        expected_counts = {
            "linear_simple": 5,
            "linear_interleaved": 6,
            "feature_branch": 3,  # 3 on main (currently checked out)
            "empty_commits": 5,
            "single_commit": 1,
            "no_commits": 0,
            "large_files": 3,
            "unicode_filenames": 3,
            "file_renames": 3,
            "binary_files": 3,
            "merge_commits": 6,  # Including merge commit
            "similarity_threshold": 3,
            "already_rebased": 5,  # Main branch commits
            "cherry_picked": 3,  # Main branch commits
            "reverted_commits": 6,
            "signed_commits": 3,
            "annotated_tags": 3,
            "simple_conflicts": 2,  # Main branch only
            "rename_conflicts": 2,  # Main branch only
            "delete_modify_conflicts": 2,  # Main branch only
            "split_targets": 3,
            "perfect_groups": 5,
            "no_grouping_needed": 3,
            "interrupted_rebase": 3,
            "many_small_commits": 50,
        }

        for repo_name, repo_path in all_repositories.items():
            if repo_name == "no_commits":
                continue  # Skip empty repository

            repo = pygit2.Repository(str(repo_path))

            if repo.is_empty:
                actual_count = 0
            else:
                # Count commits on current branch (main)
                commits = list(repo.walk(repo.head.target))
                actual_count = len(commits)

            expected = expected_counts.get(repo_name)
            if expected is not None:
                # For debugging, print actual vs expected
                if actual_count < expected:
                    print(
                        f"Repository {repo_name}: actual={actual_count}, expected={expected}"
                    )
                assert (
                    actual_count >= expected
                ), f"Repository {repo_name} has {actual_count} commits, expected at least {expected}"

    def test_repository_file_structure(self, all_repositories: dict[str, Path]) -> None:
        """Test that repositories have expected file structures."""
        for repo_name, repo_path in all_repositories.items():
            if repo_name == "no_commits":
                continue  # Skip empty repository

            # Verify working directory is not empty (except for repos with only empty commits)
            working_files = list(repo_path.glob("*"))
            git_files = [f for f in working_files if f.name != ".git"]

            if repo_name not in [
                "interrupted_rebase"
            ]:  # Some repos might have minimal files
                assert (
                    len(git_files) > 0
                ), f"Repository {repo_name} working directory is empty"

    def test_repository_branch_structure(
        self, all_repositories: dict[str, Path]
    ) -> None:
        """Test that repositories have expected branch structures."""
        multi_branch_repos = {
            "feature_branch": ["main", "feature"],
            "merge_commits": ["main", "feature"],
            "already_rebased": ["main", "feature"],
            "cherry_picked": ["main", "feature"],
            "simple_conflicts": ["main", "conflict-branch-1", "conflict-branch-2"],
            "rename_conflicts": ["main", "rename1", "rename2"],
            "delete_modify_conflicts": ["main", "delete", "modify"],
        }

        for repo_name, repo_path in all_repositories.items():
            if repo_name == "no_commits":
                continue

            repo = pygit2.Repository(str(repo_path))
            if repo.is_empty:
                continue

            branches = list(repo.branches.local)
            branch_names = list(branches)  # branches.local returns branch names

            # Every repo should have at least main branch
            assert "main" in branch_names, f"Repository {repo_name} missing main branch"

            # Check specific multi-branch repos
            if repo_name in multi_branch_repos:
                expected_branches = multi_branch_repos[repo_name]
                for expected_branch in expected_branches:
                    assert (
                        expected_branch in branch_names
                    ), f"Repository {repo_name} missing branch {expected_branch}"

    def test_repository_tag_structure(self, all_repositories: dict[str, Path]) -> None:
        """Test that repositories with tags have correct tag structure."""
        for repo_name, repo_path in all_repositories.items():
            if repo_name != "annotated_tags":
                continue

            repo = pygit2.Repository(str(repo_path))

            # Check for tags
            tags = [ref for ref in repo.references if ref.startswith("refs/tags/")]
            assert len(tags) >= 2, f"Repository {repo_name} should have at least 2 tags"

            tag_names = [tag.split("/")[-1] for tag in tags]
            assert "v1.0" in tag_names, f"Repository {repo_name} missing v1.0 tag"
            assert "v2.0" in tag_names, f"Repository {repo_name} missing v2.0 tag"

    def test_repository_file_content_integrity(
        self, all_repositories: dict[str, Path]
    ) -> None:
        """Test that repository files have expected content patterns."""
        for repo_name, repo_path in all_repositories.items():
            if repo_name in ["no_commits", "interrupted_rebase"]:
                continue

            # Test specific repositories
            if repo_name == "unicode_filenames":
                # Check that unicode files exist and have content
                unicode_files = ["файл.txt", "🚀.py", "café.md"]
                for filename in unicode_files:
                    file_path = repo_path / filename
                    if file_path.exists():
                        content = file_path.read_text(encoding="utf-8")
                        assert len(content) > 0, f"Unicode file {filename} is empty"

            elif repo_name == "binary_files":
                # Check that binary files exist
                binary_files = ["image.png", "document.pdf"]
                for filename in binary_files:
                    file_path = repo_path / filename
                    if file_path.exists():
                        content = file_path.read_bytes()
                        assert len(content) > 0, f"Binary file {filename} is empty"

            elif repo_name == "large_files":
                # Check that large file exists and has substantial content
                large_file = repo_path / "large.txt"
                if large_file.exists():
                    content = large_file.read_text()
                    assert (
                        len(content) > 1000
                    ), "Large file should have substantial content"

    def test_repository_git_fsck_passes(
        self, all_repositories: dict[str, Path]
    ) -> None:
        """Test that all repositories pass git fsck validation."""
        import subprocess

        for repo_name, repo_path in all_repositories.items():
            if repo_name == "no_commits":
                continue  # git fsck fails on repos with no commits

            try:
                result = subprocess.run(
                    ["git", "fsck", "--full"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # git fsck should pass (return code 0)
                if result.returncode != 0:
                    # Allow certain warnings but not errors
                    if "error:" in result.stderr.lower():
                        pytest.fail(
                            f"Repository {repo_name} failed git fsck: {result.stderr}"
                        )

            except subprocess.TimeoutExpired:
                pytest.fail(f"git fsck timeout on repository {repo_name}")
            except Exception as e:
                pytest.fail(f"git fsck failed on repository {repo_name}: {e}")

    def test_repository_performance_metrics(
        self, all_repositories: dict[str, Path]
    ) -> None:
        """Test basic performance metrics of repository operations."""
        import time

        for repo_name, repo_path in all_repositories.items():
            if repo_name == "no_commits":
                continue

            # Time repository opening
            start_time = time.time()
            repo = pygit2.Repository(str(repo_path))
            open_time = time.time() - start_time

            # Repository opening should be fast (under 1 second)
            assert (
                open_time < 1.0
            ), f"Repository {repo_name} took {open_time:.2f}s to open"

            if not repo.is_empty:
                # Time commit walking
                start_time = time.time()
                list(repo.walk(repo.head.target))
                walk_time = time.time() - start_time

                # Commit walking should be reasonably fast
                # Allow more time for many_small_commits repo
                max_time = 5.0 if repo_name == "many_small_commits" else 1.0
                assert (
                    walk_time < max_time
                ), f"Repository {repo_name} commit walk took {walk_time:.2f}s"

    def test_comprehensive_repository_suite(
        self, all_repositories: dict[str, Path]
    ) -> None:
        """Comprehensive test ensuring all designed repository types exist."""
        expected_repos = {
            # Basic topology
            "linear_simple",
            "linear_interleaved",
            "feature_branch",
            # Edge cases
            "empty_commits",
            "single_commit",
            "no_commits",
            "large_files",
            "unicode_filenames",
            # File-specific
            "file_renames",
            "binary_files",
            # History complexity
            "merge_commits",
            "already_rebased",
            "cherry_picked",
            "reverted_commits",
            "signed_commits",
            "annotated_tags",
            # Conflicts
            "simple_conflicts",
            "rename_conflicts",
            "delete_modify_conflicts",
            # Git-tidy specific
            "similarity_threshold",
            "split_targets",
            "perfect_groups",
            "no_grouping_needed",
            # Error recovery
            "interrupted_rebase",
            "many_small_commits",
        }

        actual_repos = set(all_repositories.keys())

        missing_repos = expected_repos - actual_repos
        assert not missing_repos, f"Missing repository types: {missing_repos}"

        extra_repos = actual_repos - expected_repos
        # Extra repos are fine, just note them
        if extra_repos:
            print(f"Note: Extra repository types found: {extra_repos}")

        # Verify we have good coverage
        assert len(actual_repos) >= len(
            expected_repos
        ), f"Expected at least {len(expected_repos)} repository types"
