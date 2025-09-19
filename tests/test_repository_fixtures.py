"""Test repository fixtures for comprehensive git-tidy testing."""

import tempfile
from pathlib import Path
from typing import Optional

import pygit2
import pytest


class RepositoryBuilder:
    """Utility class for building test git repositories."""

    def __init__(self, repo_path: Path):
        """Initialize repository builder."""
        self.repo_path = repo_path
        self.repo = pygit2.init_repository(str(repo_path), bare=False)
        self.author = pygit2.Signature("Test Author", "test@example.com")
        self.committer = pygit2.Signature("Test Committer", "test@example.com")

    def create_file(self, path: str, content: str) -> Path:
        """Create a file with given content."""
        file_path = self.repo_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path

    def add_and_commit(
        self, files: dict[str, str], message: str, empty: bool = False
    ) -> pygit2.Oid:
        """Add files and create a commit."""
        if not empty:
            for file_path, content in files.items():
                self.create_file(file_path, content)
                self.repo.index.add(file_path)

        # Write index to tree
        tree_id = self.repo.index.write_tree()

        # Get parent commit (if any)
        try:
            parent = self.repo.head.target
            parents = [parent]
        except pygit2.GitError:
            parents = []

        # Create commit
        commit_id = self.repo.create_commit(
            "HEAD", self.author, self.committer, message, tree_id, parents
        )

        return commit_id

    def create_branch(self, name: str, target: Optional[str] = None) -> pygit2.Branch:
        """Create a new branch."""
        if target is None:
            target = self.repo.head.target
        else:
            target = self.repo.revparse_single(target).id

        branch = self.repo.branches.local.create(name, self.repo[target])
        return branch

    def checkout_branch(self, name: str) -> None:
        """Checkout a branch."""
        branch = self.repo.branches[name]
        ref = self.repo.lookup_reference(branch.name)
        # Use force checkout to avoid conflicts
        self.repo.checkout(ref, strategy=pygit2.GIT_CHECKOUT_FORCE)

    def create_tag(
        self, name: str, target: Optional[str] = None, annotated: bool = False
    ) -> None:
        """Create a tag."""
        if target is None:
            target = self.repo.head.target
        else:
            target = self.repo.revparse_single(target).id

        if annotated:
            self.repo.create_tag(
                name, target, pygit2.GIT_OBJECT_COMMIT, self.author, f"Tag {name}"
            )
        else:
            self.repo.references.create(f"refs/tags/{name}", target)

    def merge_branch(self, branch_name: str, strategy: str = "recursive") -> pygit2.Oid:
        """Merge a branch."""
        branch = self.repo.branches[branch_name]
        merge_result, _ = self.repo.merge_analysis(branch.target)

        if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
            return self.repo.head.target

        if merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
            # Fast-forward merge
            self.repo.checkout_tree(self.repo.get(branch.target))
            master_ref = self.repo.lookup_reference("HEAD").resolve()
            master_ref.set_target(branch.target)
            return branch.target

        # Perform actual merge
        self.repo.merge(branch.target)

        # Check if there are conflicts
        if self.repo.index.conflicts is not None:
            # For test purposes, we'll resolve conflicts by taking "ours"
            for conflict in self.repo.index.conflicts:
                if conflict[0] is not None:  # ancestor
                    self.repo.index.add(conflict[0])

        # Create merge commit
        tree_id = self.repo.index.write_tree()
        commit_id = self.repo.create_commit(
            "HEAD",
            self.author,
            self.committer,
            f"Merge branch '{branch_name}'",
            tree_id,
            [self.repo.head.target, branch.target],
        )

        self.repo.state_cleanup()
        return commit_id


class TestRepositoryFixtures:
    """Test class containing all repository fixture generators."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for repositories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    def create_repo_linear_simple(self, base_path: Path) -> Path:
        """Create a simple linear repository: A---B---C---D---E (main)."""
        repo_path = base_path / "repo_linear_simple"
        builder = RepositoryBuilder(repo_path)

        # Create 5 commits, each touching different files
        builder.add_and_commit(
            {"file1.py": "print('hello from file1')"}, "A: Add file1"
        )
        builder.add_and_commit(
            {"file2.py": "print('hello from file2')"}, "B: Add file2"
        )
        builder.add_and_commit(
            {"file3.py": "print('hello from file3')"}, "C: Add file3"
        )
        builder.add_and_commit(
            {"file4.py": "print('hello from file4')"}, "D: Add file4"
        )
        builder.add_and_commit(
            {"file5.py": "print('hello from file5')"}, "E: Add file5"
        )

        return repo_path

    def create_repo_linear_interleaved(self, base_path: Path) -> Path:
        """Create interleaved linear repository with file patterns."""
        repo_path = base_path / "repo_linear_interleaved"
        builder = RepositoryBuilder(repo_path)

        # Pattern: A(file1), B(file2), C(file1), D(file3), E(file1), F(file2)
        builder.add_and_commit({"file1.py": "# Initial file1"}, "A: Add file1")
        builder.add_and_commit({"file2.py": "# Initial file2"}, "B: Add file2")
        builder.add_and_commit(
            {"file1.py": "# Modified file1\nprint('update')"}, "C: Update file1"
        )
        builder.add_and_commit({"file3.py": "# Initial file3"}, "D: Add file3")
        builder.add_and_commit(
            {"file1.py": "# Modified file1\nprint('update')\nprint('more changes')"},
            "E: Update file1 again",
        )
        builder.add_and_commit(
            {"file2.py": "# Modified file2\nprint('update')"}, "F: Update file2"
        )

        return repo_path

    def create_repo_feature_branch(self, base_path: Path) -> Path:
        """Create repository with feature branch: main with feature branch."""
        repo_path = base_path / "repo_feature_branch"
        builder = RepositoryBuilder(repo_path)

        # Create main branch commits
        builder.add_and_commit({"main.py": "# Main file"}, "A: Initial commit")
        builder.add_and_commit({"utils.py": "# Utility functions"}, "B: Add utilities")
        builder.add_and_commit({"config.py": "# Configuration"}, "C: Add config")

        # Create feature branch
        builder.create_branch("feature")
        builder.checkout_branch("feature")

        builder.add_and_commit(
            {"feature.py": "# Feature implementation"}, "D: Add feature"
        )
        builder.add_and_commit(
            {"feature.py": "# Feature implementation\ndef feature_func():\n    pass"},
            "E: Implement feature",
        )
        builder.add_and_commit({"tests.py": "# Feature tests"}, "F: Add feature tests")

        # Return to main
        builder.checkout_branch("main")

        return repo_path

    def create_repo_empty_commits(self, base_path: Path) -> Path:
        """Create repository with empty commits."""
        repo_path = base_path / "repo_empty_commits"
        builder = RepositoryBuilder(repo_path)

        builder.add_and_commit({"file1.py": "# Initial"}, "A: Initial commit")
        builder.add_and_commit({}, "B: Empty commit", empty=True)
        builder.add_and_commit({"file1.py": "# Initial\n# Updated"}, "C: Update file1")
        builder.add_and_commit({}, "D: Another empty commit", empty=True)
        builder.add_and_commit({"file2.py": "# New file"}, "E: Add file2")

        return repo_path

    def create_repo_single_commit(self, base_path: Path) -> Path:
        """Create repository with only one commit."""
        repo_path = base_path / "repo_single_commit"
        builder = RepositoryBuilder(repo_path)

        builder.add_and_commit(
            {"readme.txt": "# Single commit repo"}, "A: Initial commit"
        )

        return repo_path

    def create_repo_no_commits(self, base_path: Path) -> Path:
        """Create empty repository with no commits."""
        repo_path = base_path / "repo_no_commits"
        pygit2.init_repository(str(repo_path), bare=False)
        return repo_path

    def create_repo_large_files(self, base_path: Path) -> Path:
        """Create repository with large files."""
        repo_path = base_path / "repo_large_files"
        builder = RepositoryBuilder(repo_path)

        # Create large file content (simulated)
        large_content = "x" * 10000  # 10KB file (scaled down for testing)

        builder.add_and_commit({"large.txt": large_content}, "A: Add large file")

        # Modify large file
        builder.add_and_commit(
            {"large.txt": large_content + "\n# Modified"}, "B: Modify large file"
        )

        # Add small files
        builder.add_and_commit(
            {"small1.py": "print('small')", "small2.py": "print('small2')"},
            "C: Add small files",
        )

        return repo_path

    def create_repo_unicode_filenames(self, base_path: Path) -> Path:
        """Create repository with unicode filenames."""
        repo_path = base_path / "repo_unicode_filenames"
        builder = RepositoryBuilder(repo_path)

        # Unicode filenames
        builder.add_and_commit({"файл.txt": "Русский текст"}, "A: Add Russian file")
        builder.add_and_commit({"🚀.py": "print('rocket')"}, "B: Add emoji file")
        builder.add_and_commit(
            {"café.md": "# Café documentation"}, "C: Add French file"
        )

        return repo_path

    def create_repo_file_renames(self, base_path: Path) -> Path:
        """Create repository with file renames."""
        repo_path = base_path / "repo_file_renames"
        builder = RepositoryBuilder(repo_path)

        # Create initial file
        builder.add_and_commit({"file.txt": "Initial content"}, "A: Create file")

        # Rename file (simulate by removing old and adding new)
        (repo_path / "file.txt").unlink()
        builder.repo.index.remove("file.txt")
        builder.add_and_commit(
            {"new.txt": "Initial content"}, "B: Rename file.txt to new.txt"
        )

        # Modify renamed file
        builder.add_and_commit(
            {"new.txt": "Initial content\nModified"}, "C: Modify renamed file"
        )

        return repo_path

    def create_repo_binary_files(self, base_path: Path) -> Path:
        """Create repository with binary files."""
        repo_path = base_path / "repo_binary_files"
        builder = RepositoryBuilder(repo_path)

        # Create binary files
        image_data = bytes(range(256))
        pdf_data = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"

        # Write binary files manually since create_file expects text
        (repo_path / "image.png").write_bytes(image_data)
        builder.repo.index.add("image.png")
        builder.add_and_commit({}, "A: Add image", empty=True)

        (repo_path / "document.pdf").write_bytes(pdf_data)
        builder.repo.index.add("document.pdf")
        builder.add_and_commit({}, "B: Add PDF", empty=True)

        builder.add_and_commit({"text.txt": "Regular text file"}, "C: Add text file")

        return repo_path

    def create_repo_merge_commits(self, base_path: Path) -> Path:
        """Create repository with merge commits."""
        repo_path = base_path / "repo_merge_commits"
        builder = RepositoryBuilder(repo_path)

        # Main branch
        builder.add_and_commit({"main.py": "# Main"}, "A: Initial")
        builder.add_and_commit({"main.py": "# Main\n# Updated"}, "B: Update main")
        builder.add_and_commit({"shared.py": "# Shared"}, "C: Add shared")

        # Create feature branch
        builder.create_branch("feature")
        builder.checkout_branch("feature")

        builder.add_and_commit({"feature.py": "# Feature"}, "D: Add feature")
        builder.add_and_commit(
            {"feature.py": "# Feature\n# Enhanced"}, "E: Enhance feature"
        )

        # Return to main and merge
        builder.checkout_branch("main")
        builder.merge_branch("feature")

        # Continue on main
        builder.add_and_commit(
            {"main.py": "# Main\n# Updated\n# Post-merge"}, "G: Post-merge update"
        )

        return repo_path

    def create_repo_similarity_threshold(self, base_path: Path) -> Path:
        """Create repository for testing similarity thresholds."""
        repo_path = base_path / "repo_similarity_threshold"
        builder = RepositoryBuilder(repo_path)

        # Create base file with 100 lines
        base_content = "\n".join([f"line {i}" for i in range(100)])
        builder.add_and_commit({"file1.py": base_content}, "A: Create base file")

        # Modify with 1 line change (99% similarity)
        modified_content = base_content + "\nline 100"
        builder.add_and_commit({"file1.py": modified_content}, "B: Minor change")

        # Create file with 50% similar content
        similar_content = (
            "\n".join([f"line {i}" for i in range(50)])
            + "\n"
            + "\n".join([f"different {i}" for i in range(50)])
        )
        builder.add_and_commit({"file2.py": similar_content}, "C: Create similar file")

        return repo_path

    def create_all_repositories(self, base_path: Path) -> dict[str, Path]:
        """Create all test repositories."""
        repositories = {}

        # Basic topology repositories
        repositories["linear_simple"] = self.create_repo_linear_simple(base_path)
        repositories["linear_interleaved"] = self.create_repo_linear_interleaved(
            base_path
        )
        repositories["feature_branch"] = self.create_repo_feature_branch(base_path)

        # Edge case repositories
        repositories["empty_commits"] = self.create_repo_empty_commits(base_path)
        repositories["single_commit"] = self.create_repo_single_commit(base_path)
        repositories["no_commits"] = self.create_repo_no_commits(base_path)
        repositories["large_files"] = self.create_repo_large_files(base_path)
        repositories["unicode_filenames"] = self.create_repo_unicode_filenames(
            base_path
        )

        # File-specific scenarios
        repositories["file_renames"] = self.create_repo_file_renames(base_path)
        repositories["binary_files"] = self.create_repo_binary_files(base_path)

        # History complexity
        repositories["merge_commits"] = self.create_repo_merge_commits(base_path)

        # Git-tidy specific
        repositories["similarity_threshold"] = self.create_repo_similarity_threshold(
            base_path
        )

        return repositories

    def test_repository_creation(self, temp_dir: Path) -> None:
        """Test that all repositories can be created successfully."""
        repositories = self.create_all_repositories(temp_dir)

        # Verify all repositories were created
        assert len(repositories) > 0

        for repo_name, repo_path in repositories.items():
            assert repo_path.exists(), f"Repository {repo_name} was not created"
            assert (
                repo_path / ".git"
            ).exists(), f"Repository {repo_name} is not a git repository"

            # Open repository and verify it's valid
            repo = pygit2.Repository(str(repo_path))
            assert repo is not None, f"Could not open repository {repo_name}"

            # Verify repository is not empty (except for no_commits)
            if repo_name != "no_commits":
                assert (
                    not repo.is_empty
                ), f"Repository {repo_name} is unexpectedly empty"
            else:
                assert repo.is_empty, f"Repository {repo_name} should be empty"

    def test_linear_simple_structure(self, temp_dir: Path) -> None:
        """Test the structure of the linear simple repository."""
        repo_path = self.create_repo_linear_simple(temp_dir)
        repo = pygit2.Repository(str(repo_path))

        # Count commits
        commits = list(repo.walk(repo.head.target))
        assert len(commits) == 5, "Linear simple repo should have 5 commits"

        # Verify files exist
        for i in range(1, 6):
            assert (repo_path / f"file{i}.py").exists(), f"file{i}.py should exist"

    def test_feature_branch_structure(self, temp_dir: Path) -> None:
        """Test the structure of the feature branch repository."""
        repo_path = self.create_repo_feature_branch(temp_dir)
        repo = pygit2.Repository(str(repo_path))

        # Verify branches exist
        branches = list(repo.branches.local)
        branch_names = list(branches)  # branches.local returns branch names
        assert "main" in branch_names, "main branch should exist"
        assert "feature" in branch_names, "feature branch should exist"

        # Verify we're on main branch
        assert repo.head.shorthand == "main", "Should be on main branch"

    def test_empty_commits_structure(self, temp_dir: Path) -> None:
        """Test repository with empty commits."""
        repo_path = self.create_repo_empty_commits(temp_dir)
        repo = pygit2.Repository(str(repo_path))

        commits = list(repo.walk(repo.head.target))
        assert len(commits) == 5, "Should have 5 commits total"

        # Check for empty commits by examining tree changes
        for i, commit in enumerate(reversed(commits)):
            if i in [1, 3]:  # B and D are empty commits
                if len(commit.parents) > 0:
                    parent = commit.parents[0]
                    # Empty commits should have same tree as parent
                    assert (
                        commit.tree.id == parent.tree.id
                    ), f"Commit {i} should be empty"
