"""Сканер файловой системы проекта."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from dataclasses import dataclass, field


DEFAULT_IGNORE = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "*.egg-info",
    ".tox",
    ".eggs",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".md",
    ".rst",
    ".txt",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".sql",
    ".graphql",
    ".proto",
    ".xml",
    ".svg",
    ".dockerfile",
    ".dockerignore",
    ".gitignore",
    ".env",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".lua",
    ".r",
    ".jl",
    ".vue",
    ".svelte",
    ".astro",
}


@dataclass
class FileNode:
    """Узел дерева файлов."""

    path: Path
    name: str
    is_dir: bool
    children: list[FileNode] = field(default_factory=list)
    checked: bool = False
    size: int = 0


class FsScanner:
    """Сканирует директорию проекта, строит дерево."""

    def __init__(self, ignore_patterns: set[str] | None = None):
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE

    def scan(self, root: Path, max_depth: int = 10) -> FileNode:
        """Построить дерево файлов."""
        return self._scan_dir(root, root, depth=0, max_depth=max_depth)

    def _scan_dir(self, path: Path, root: Path, depth: int, max_depth: int) -> FileNode:
        node = FileNode(
            path=path,
            name=path.name or str(path),
            is_dir=True,
        )

        if depth >= max_depth:
            return node

        try:
            entries = sorted(
                path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            return node

        for entry in entries:
            if self._should_ignore(entry.name):
                continue

            if entry.is_dir():
                child = self._scan_dir(entry, root, depth + 1, max_depth)
                if child.children:  # Только непустые директории
                    node.children.append(child)
            elif entry.is_file() and self._is_text_file(entry):
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                node.children.append(
                    FileNode(
                        path=entry,
                        name=entry.name,
                        is_dir=False,
                        size=size,
                    )
                )

        return node

    def _should_ignore(self, name: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    @staticmethod
    def _is_text_file(path: Path) -> bool:
        if path.suffix.lower() in TEXT_EXTENSIONS:
            return True
        if path.name.lower() in {
            "makefile",
            "dockerfile",
            "procfile",
            "gemfile",
            "rakefile",
            "vagrantfile",
            "justfile",
        }:
            return True
        if not path.suffix:
            return False
        return False

    @staticmethod
    def read_file(path: Path, max_size: int = 512_000) -> str | None:
        """Прочитать текстовый файл."""
        try:
            if path.stat().st_size > max_size:
                return f"[File too large: {path.stat().st_size:,} bytes]"
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[Error reading file: {e}]"
