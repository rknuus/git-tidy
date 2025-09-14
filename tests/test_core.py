"""Tests for git-tidy core functionality."""

from git_tidy.core import GitTidy


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
