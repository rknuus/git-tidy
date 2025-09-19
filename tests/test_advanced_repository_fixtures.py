"""Advanced test repository fixtures for complex git-tidy scenarios."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import pygit2
import pytest

from .test_repository_fixtures import RepositoryBuilder


class AdvancedRepositoryBuilder(RepositoryBuilder):
    """Extended repository builder for complex scenarios."""

    def cherry_pick_commit(self, commit_sha: str) -> pygit2.Oid:
        """Cherry-pick a commit using git CLI (pygit2 doesn't support cherry-pick directly)."""
        subprocess.run(
            ["git", "cherry-pick", commit_sha],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        return self.repo.head.target

    def revert_commit(self, commit_sha: str) -> pygit2.Oid:
        """Revert a commit using git CLI."""
        subprocess.run(
            ["git", "revert", "--no-edit", commit_sha],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        return self.repo.head.target

    def create_signed_commit(
        self, files: dict[str, str], message: str, gpg_key: Optional[str] = None
    ) -> pygit2.Oid:
        """Create a GPG-signed commit (simulated with special commit message)."""
        # For testing purposes, we'll simulate signed commits with special markers
        signed_message = f"{message}\n\nSigned-off-by: Test Author <test@example.com>"
        return self.add_and_commit(files, signed_message)

    def create_conflicting_branches(self) -> tuple[str, str]:
        """Create two branches that will conflict when merged."""
        # Create first branch
        branch1 = "conflict-branch-1"
        self.create_branch(branch1)
        self.checkout_branch(branch1)

        self.add_and_commit(
            {"conflict.txt": "Line 1\nBranch 1 content\nLine 3"}, "Branch 1 changes"
        )

        # Return to main and create second branch
        self.checkout_branch("main")
        branch2 = "conflict-branch-2"
        self.create_branch(branch2)
        self.checkout_branch(branch2)

        self.add_and_commit(
            {"conflict.txt": "Line 1\nBranch 2 content\nLine 3"}, "Branch 2 changes"
        )

        # Return to main
        self.checkout_branch("main")

        return branch1, branch2

    def simulate_interrupted_rebase(self) -> None:
        """Simulate an interrupted rebase state."""
        # Create rebase directory structure
        git_dir = self.repo_path / ".git"
        rebase_dir = git_dir / "rebase-apply"
        rebase_dir.mkdir(exist_ok=True)

        # Create files that git creates during rebase
        (rebase_dir / "head-name").write_text("refs/heads/main")
        (rebase_dir / "onto").write_text(str(self.repo.head.target))
        (rebase_dir / "orig-head").write_text(str(self.repo.head.target))


class TestAdvancedRepositoryFixtures:
    """Test class for advanced repository scenarios."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for repositories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    def create_repo_already_rebased(self, base_path: Path) -> Path:
        """Create repository with already rebased content."""
        repo_path = base_path / "repo_already_rebased"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Create main branch
        builder.add_and_commit({"main.py": "# Main file"}, "A: Initial")
        builder.add_and_commit({"main.py": "# Main file\n# Updated"}, "B: Update main")
        builder.add_and_commit({"shared.py": "# Shared file"}, "C: Add shared")

        # Create feature branch from A
        a_commit = list(builder.repo.walk(builder.repo.head.target))[
            -1
        ]  # Get first commit
        builder.create_branch("feature", str(a_commit.id))
        builder.checkout_branch("feature")

        # Add commits that will be "rebased"
        builder.add_and_commit(
            {"feature.py": "# Original feature"}, "D: Original feature"
        )
        builder.add_and_commit(
            {"feature.py": "# Original feature\n# Enhanced"}, "E: Enhanced feature"
        )

        # Return to main
        builder.checkout_branch("main")

        # Now create "rebased" versions on main (simulating already merged content)
        builder.add_and_commit(
            {"feature.py": "# Original feature"}, "D': Rebased feature"
        )
        builder.add_and_commit(
            {"feature.py": "# Original feature\n# Enhanced"}, "E': Rebased enhanced"
        )

        return repo_path

    def create_repo_cherry_picked(self, base_path: Path) -> Path:
        """Create repository with cherry-picked commits."""
        repo_path = base_path / "repo_cherry_picked"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Create main branch
        builder.add_and_commit({"main.py": "# Main"}, "A: Initial")
        builder.add_and_commit({"utils.py": "# Utils"}, "B: Add utils")

        # Create feature branch
        builder.create_branch("feature")
        builder.checkout_branch("feature")

        builder.add_and_commit({"feature1.py": "# Feature 1"}, "X: Feature 1")
        builder.add_and_commit({"feature2.py": "# Feature 2"}, "Y: Feature 2")
        builder.add_and_commit({"feature3.py": "# Feature 3"}, "Z: Feature 3")

        # Return to main and cherry-pick X as D
        builder.checkout_branch("main")
        builder.add_and_commit(
            {"feature1.py": "# Feature 1"}, "D: Cherry-picked feature 1"
        )

        return repo_path

    def create_repo_reverted_commits(self, base_path: Path) -> Path:
        """Create repository with reverted commits."""
        repo_path = base_path / "repo_reverted_commits"
        builder = AdvancedRepositoryBuilder(repo_path)

        builder.add_and_commit({"file1.py": "# Initial"}, "A: Initial")
        builder.add_and_commit({"file2.py": "# Second file"}, "B: Add file2")
        builder.add_and_commit(
            {"file1.py": "# Initial\n# Bug introduced"}, "C: Introduce bug"
        )
        builder.add_and_commit({"file3.py": "# Third file"}, "D: Add file3")

        # Revert commit C
        builder.add_and_commit({"file1.py": "# Initial"}, "Revert C: Remove bug")
        builder.add_and_commit({"file4.py": "# Fourth file"}, "E: Continue development")

        return repo_path

    def create_repo_signed_commits(self, base_path: Path) -> Path:
        """Create repository with mix of signed and unsigned commits."""
        repo_path = base_path / "repo_signed_commits"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Signed commits (simulated)
        builder.create_signed_commit({"file1.py": "# Signed file"}, "A: Signed commit")
        builder.create_signed_commit(
            {"file2.py": "# Another signed"}, "B: Another signed commit"
        )

        # Unsigned commit
        builder.add_and_commit({"file3.py": "# Unsigned file"}, "C: Unsigned commit")

        return repo_path

    def create_repo_annotated_tags(self, base_path: Path) -> Path:
        """Create repository with annotated tags."""
        repo_path = base_path / "repo_annotated_tags"
        builder = AdvancedRepositoryBuilder(repo_path)

        builder.add_and_commit({"version1.py": "VERSION = '1.0'"}, "A: Version 1.0")
        commit_a = builder.repo.head.target

        builder.add_and_commit({"version1.py": "VERSION = '1.1'"}, "B: Version 1.1")
        commit_b = builder.repo.head.target

        builder.add_and_commit({"version1.py": "VERSION = '2.0'"}, "C: Version 2.0")

        # Create annotated tags
        builder.create_tag("v1.0", str(commit_a), annotated=True)
        builder.create_tag("v2.0", str(commit_b), annotated=True)

        return repo_path

    def create_repo_simple_conflicts(self, base_path: Path) -> Path:
        """Create repository set up for simple conflicts."""
        repo_path = base_path / "repo_simple_conflicts"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Create base
        builder.add_and_commit(
            {"conflict.txt": "Line 1\nLine 2\nLine 3"}, "A: Base file"
        )
        builder.add_and_commit({"other.py": "# Other file"}, "B: Other file")

        # Create conflicting branches
        branch1, branch2 = builder.create_conflicting_branches()

        return repo_path

    def create_repo_rename_conflicts(self, base_path: Path) -> Path:
        """Create repository with rename conflicts."""
        repo_path = base_path / "repo_rename_conflicts"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Create base
        builder.add_and_commit({"original.txt": "Original content"}, "A: Create file")
        builder.add_and_commit({"other.py": "# Other file"}, "B: Other file")

        # Create branch 1 - rename to new1.txt
        builder.create_branch("rename1")
        builder.checkout_branch("rename1")
        (repo_path / "original.txt").unlink()
        builder.repo.index.remove("original.txt")
        builder.add_and_commit(
            {"new1.txt": "Original content"}, "D: Rename to new1.txt"
        )

        # Create branch 2 - rename to new2.txt
        builder.checkout_branch("main")
        builder.create_branch("rename2")
        builder.checkout_branch("rename2")
        (repo_path / "original.txt").unlink()
        builder.repo.index.remove("original.txt")
        builder.add_and_commit(
            {"new2.txt": "Original content"}, "E: Rename to new2.txt"
        )

        builder.checkout_branch("main")
        return repo_path

    def create_repo_delete_modify_conflicts(self, base_path: Path) -> Path:
        """Create repository with delete vs modify conflicts."""
        repo_path = base_path / "repo_delete_modify_conflicts"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Create base
        builder.add_and_commit(
            {"target.txt": "Content to be modified/deleted"}, "A: Create target"
        )
        builder.add_and_commit({"other.py": "# Other file"}, "B: Other file")

        # Branch 1: Delete the file
        builder.create_branch("delete")
        builder.checkout_branch("delete")
        (repo_path / "target.txt").unlink()
        builder.repo.index.remove("target.txt")
        builder.add_and_commit({}, "D: Delete target file", empty=True)

        # Branch 2: Modify the file
        builder.checkout_branch("main")
        builder.create_branch("modify")
        builder.checkout_branch("modify")
        builder.add_and_commit(
            {"target.txt": "Content to be modified/deleted\nModified content"},
            "E: Modify target file",
        )

        builder.checkout_branch("main")
        return repo_path

    def create_repo_split_targets(self, base_path: Path) -> Path:
        """Create repository ideal for split-commits testing."""
        repo_path = base_path / "repo_split_targets"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Create commits that touch multiple files
        builder.add_and_commit(
            {"auth.py": "# Authentication module", "ui.py": "# User interface module"},
            "A: Add auth and UI modules",
        )

        builder.add_and_commit(
            {
                "auth.py": "# Authentication module\ndef login(): pass",
                "database.py": "# Database module",
            },
            "B: Enhance auth, add database",
        )

        builder.add_and_commit(
            {
                "ui.py": "# User interface module\ndef render(): pass",
                "database.py": "# Database module\ndef connect(): pass",
            },
            "C: Enhance UI and database",
        )

        return repo_path

    def create_repo_perfect_groups(self, base_path: Path) -> Path:
        """Create repository with perfect file-based grouping."""
        repo_path = base_path / "repo_perfect_groups"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Perfect grouping pattern: auth, ui, auth, ui, auth
        builder.add_and_commit({"auth.py": "# Auth v1"}, "A: Initial auth")
        builder.add_and_commit({"ui.py": "# UI v1"}, "B: Initial UI")
        builder.add_and_commit({"auth.py": "# Auth v1\n# Auth v2"}, "C: Update auth")
        builder.add_and_commit({"ui.py": "# UI v1\n# UI v2"}, "D: Update UI")
        builder.add_and_commit(
            {"auth.py": "# Auth v1\n# Auth v2\n# Auth v3"}, "E: Final auth"
        )

        return repo_path

    def create_repo_no_grouping_needed(self, base_path: Path) -> Path:
        """Create repository already perfectly grouped."""
        repo_path = base_path / "repo_no_grouping_needed"
        builder = AdvancedRepositoryBuilder(repo_path)

        builder.add_and_commit({"file1.py": "# File 1"}, "A: Add file1")
        builder.add_and_commit({"file2.py": "# File 2"}, "B: Add file2")
        builder.add_and_commit({"file3.py": "# File 3"}, "C: Add file3")

        return repo_path

    def create_repo_interrupted_rebase(self, base_path: Path) -> Path:
        """Create repository with interrupted rebase state."""
        repo_path = base_path / "repo_interrupted_rebase"
        builder = AdvancedRepositoryBuilder(repo_path)

        builder.add_and_commit({"main.py": "# Main"}, "A: Initial")
        builder.add_and_commit({"feature.py": "# Feature"}, "B: Add feature")
        builder.add_and_commit({"main.py": "# Main\n# Updated"}, "C: Update main")

        # Simulate interrupted rebase
        builder.simulate_interrupted_rebase()

        return repo_path

    def create_repo_many_small_commits(self, base_path: Path) -> Path:
        """Create repository with many small commits for performance testing."""
        repo_path = base_path / "repo_many_small_commits"
        builder = AdvancedRepositoryBuilder(repo_path)

        # Create 50 small commits (reduced from 100+ for reasonable test time)
        for i in range(50):
            builder.add_and_commit(
                {f"file_{i % 5}.py": f"# File {i % 5}\n# Update {i}"},
                f"Commit {i}: Update file {i % 5}",
            )

        return repo_path

    def create_all_advanced_repositories(self, base_path: Path) -> dict[str, Path]:
        """Create all advanced test repositories."""
        repositories = {}

        # History complexity scenarios
        repositories["already_rebased"] = self.create_repo_already_rebased(base_path)
        repositories["cherry_picked"] = self.create_repo_cherry_picked(base_path)
        repositories["reverted_commits"] = self.create_repo_reverted_commits(base_path)
        repositories["signed_commits"] = self.create_repo_signed_commits(base_path)
        repositories["annotated_tags"] = self.create_repo_annotated_tags(base_path)

        # Conflict scenarios
        repositories["simple_conflicts"] = self.create_repo_simple_conflicts(base_path)
        repositories["rename_conflicts"] = self.create_repo_rename_conflicts(base_path)
        repositories["delete_modify_conflicts"] = (
            self.create_repo_delete_modify_conflicts(base_path)
        )

        # Git-tidy specific scenarios
        repositories["split_targets"] = self.create_repo_split_targets(base_path)
        repositories["perfect_groups"] = self.create_repo_perfect_groups(base_path)
        repositories["no_grouping_needed"] = self.create_repo_no_grouping_needed(
            base_path
        )

        # Error recovery scenarios
        repositories["interrupted_rebase"] = self.create_repo_interrupted_rebase(
            base_path
        )
        repositories["many_small_commits"] = self.create_repo_many_small_commits(
            base_path
        )

        return repositories

    def test_advanced_repository_creation(self, temp_dir: Path) -> None:
        """Test that all advanced repositories can be created successfully."""
        repositories = self.create_all_advanced_repositories(temp_dir)

        assert len(repositories) > 0

        for repo_name, repo_path in repositories.items():
            assert repo_path.exists(), f"Repository {repo_name} was not created"
            assert (
                repo_path / ".git"
            ).exists(), f"Repository {repo_name} is not a git repository"

            # Open repository and verify it's valid
            repo = pygit2.Repository(str(repo_path))
            assert repo is not None, f"Could not open repository {repo_name}"
            assert not repo.is_empty, f"Repository {repo_name} should not be empty"

    def test_cherry_picked_structure(self, temp_dir: Path) -> None:
        """Test cherry-picked repository structure."""
        repo_path = self.create_repo_cherry_picked(temp_dir)
        repo = pygit2.Repository(str(repo_path))

        # Verify both main and feature branches exist
        branches = list(repo.branches.local)
        branch_names = list(branches)  # branches.local returns branch names
        assert "main" in branch_names
        assert "feature" in branch_names

        # Verify feature1.py exists on both branches (cherry-picked)
        assert (repo_path / "feature1.py").exists()

    def test_conflict_repository_structure(self, temp_dir: Path) -> None:
        """Test conflict repository has correct branch structure."""
        repo_path = self.create_repo_simple_conflicts(temp_dir)
        repo = pygit2.Repository(str(repo_path))

        branches = list(repo.branches.local)
        branch_names = list(branches)  # branches.local returns branch names

        assert "main" in branch_names
        assert "conflict-branch-1" in branch_names
        assert "conflict-branch-2" in branch_names

    def test_split_targets_structure(self, temp_dir: Path) -> None:
        """Test split targets repository structure."""
        repo_path = self.create_repo_split_targets(temp_dir)

        # Verify files exist
        assert (repo_path / "auth.py").exists()
        assert (repo_path / "ui.py").exists()
        assert (repo_path / "database.py").exists()

        repo = pygit2.Repository(str(repo_path))
        commits = list(repo.walk(repo.head.target))
        assert len(commits) == 3, "Should have exactly 3 commits"
