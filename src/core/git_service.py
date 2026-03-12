"""Git service to get files changed since last commit."""

import subprocess
from pathlib import Path
from typing import List


class GitService:
    """Service for Git operations."""

    def __init__(self, repo_path: Path):
        """
        Initialize Git service.

        Args:
            repo_path: Path to the git repository root.
        """
        self.repo_path = repo_path

    def _run_git_command(self, args: List[str]) -> str:
        """
        Run a git command and return output.

        Args:
            args: List of git command arguments (without 'git').

        Returns:
            Command output as string.

        Raises:
            RuntimeError: If git command fails.
        """
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {e.stderr.strip()}")

    def get_changed_files(self) -> List[Path]:
        """
        Get list of files that have been modified or added since the last commit.

        Returns:
            List of Path objects for changed files.
            Empty list if not a git repo or no changes.
        """
        try:
            # Check if it's a git repository
            if not self._is_git_repo():
                return []

            # Get files changed since last commit (HEAD)
            # --name-only: show only file names
            # --diff-filter=ACMRT: Added, Copied, Modified, Renamed, Type changed (exclude Deleted)
            output = self._run_git_command(
                ["diff", "--name-only", "--diff-filter=ACMRT", "HEAD"]
            )

            if not output.strip():
                return []

            changed_files = []
            for line in output.strip().split("\n"):
                if line.strip():
                    file_path = self.repo_path / line.strip()
                    # Only include files that actually exist (exclude deleted)
                    if file_path.exists() and file_path.is_file():
                        # Exclude binary files and common ignored patterns
                        if not self._should_exclude(file_path):
                            changed_files.append(file_path)

            return changed_files

        except (RuntimeError, Exception):
            # If any git operation fails, return empty list
            return []

    def _should_exclude(self, file_path: Path) -> bool:
        """
        Check if a file should be excluded from the list.

        Args:
            file_path: Path to the file.

        Returns:
            True if file should be excluded, False otherwise.
        """
        # Exclude common ignored patterns
        exclude_patterns = [
            "__pycache__",
            ".pyc",
            ".pyo",
            ".pyd",
            ".so",
            ".dll",
            ".egg",
            ".egg-info",
            ".eggs",
            ".dist-info",
            "node_modules",
            ".venv",
            "venv",
            ".env",
            ".git",
            ".svn",
            ".hg",
            ".tox",
            ".coverage",
            ".htmlcov",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".hypothesis",
            ".nox",
            "dist",
            "build",
        ]

        path_str = str(file_path)
        for pattern in exclude_patterns:
            if pattern in path_str:
                return True

        return False

    def _is_git_repo(self) -> bool:
        """
        Check if the current path is a git repository.

        Returns:
            True if it's a git repo, False otherwise.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False
