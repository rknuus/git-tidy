"""Git-tidy: A tool for intelligently reordering git commits by grouping them based on file similarity."""

__version__ = "0.1.0"

from .core import GitError, GitTidy

__all__ = ["GitTidy", "GitError"]
