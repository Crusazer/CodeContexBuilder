"""Git service to get files changed since last commit."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_TIMEOUT_SECONDS = 10


class GitService:
    """Service for Git operations."""

    def __init__(self, repo_path: Path):
        """
        Initialize Git service.

        Args:
            repo_path: Path to the git repository root.
        """
        self.repo_path = repo_path

    def _run_git_command(self, args: list[str]) -> str:
        """
        Run a git command and return output.

        Args:
            args: List of git command arguments (without 'git').

        Returns:
            Command output as string.

        Raises:
            RuntimeError: If git command fails or times out.
        """
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            return result.stdout
        except FileNotFoundError:
            raise RuntimeError("Git is not installed or not found in PATH")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Git command timed out after {_GIT_TIMEOUT_SECONDS}s")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else str(e)
            raise RuntimeError(f"Git command failed: {stderr}")

    def is_git_repo(self) -> bool:
        """Check if the current path is inside a git work tree.

        Returns:
            True if it's a git repo, False otherwise.

        Raises:
            RuntimeError: If git is not installed.
        """
        return self._is_git_repo()

    def get_changed_files(self) -> list[Path]:
        """
        Get list of files that have been modified or added since the last commit.

        Returns:
            List of Path objects for changed files.
            Empty list if not a git repo or no changes.

        Raises:
            RuntimeError: If git is not installed or command fails.
        """
        # Check if it's a git repository
        if not self._is_git_repo():
            return []

        # Get files changed since last commit (HEAD), including staged and unstaged
        # --relative ensures paths are relative to self.repo_path even if we are in a monorepo subfolder
        try:
            diff_output = self._run_git_command(
                ["diff", "--name-only", "--relative", "--diff-filter=ACMRT", "HEAD"]
            )
        except RuntimeError:
            # Might fail if there's no HEAD (empty repo), fallback to empty
            diff_output = ""

        # Get untracked files
        untracked_output = self._run_git_command(
            ["ls-files", "--others", "--exclude-standard"]
        )

        raw_files = diff_output.strip().split("\n") + untracked_output.strip().split(
            "\n"
        )

        changed_files = []
        seen = set()
        for line in raw_files:
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)

            file_path = (self.repo_path / line).resolve()
            # Only include files that actually exist (exclude deleted)
            if file_path.exists() and file_path.is_file():
                # Exclude binary files and common ignored patterns
                if not self._should_exclude(file_path):
                    changed_files.append(file_path)

        return changed_files

    def _should_exclude(self, file_path: Path) -> bool:
        """
        Check if a file should be excluded from the list.

        This acts as a safety net on top of .gitignore filtering.
        We check path *segments* (directory/file names), not substrings,
        to avoid false positives like ``distribution`` matching ``dist``.

        Args:
            file_path: Path to the file.

        Returns:
            True if file should be excluded, False otherwise.
        """
        exclude_names: set[str] = {
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            ".git",
            ".svn",
            ".hg",
            ".tox",
            ".nox",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".hypothesis",
            ".htmlcov",
            ".coverage",
            "dist",
            "build",
            ".eggs",
            ".egg-info",
        }
        exclude_suffixes: set[str] = {".pyc", ".pyo", ".pyd", ".so", ".dll"}

        # Check each segment of the path (directory and file names)
        for part in file_path.parts:
            if part in exclude_names:
                return True

        # Check file extension
        if file_path.suffix in exclude_suffixes:
            return True

        return False

    def _is_git_repo(self) -> bool:
        """
        Check if the current path is a git repository.

        Returns:
            True if it's a git repo, False otherwise.

        Raises:
            RuntimeError: If git is not installed.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            return result.returncode == 0
        except FileNotFoundError:
            raise RuntimeError("Git is not installed or not found in PATH")
        except subprocess.TimeoutExpired:
            logger.warning("git rev-parse timed out for %s", self.repo_path)
            return False
        except OSError:
            return False
