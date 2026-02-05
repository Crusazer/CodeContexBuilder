import os
from pathlib import Path
from typing import List, Optional

import pathspec

from src.models.schemas import FileNode


class ProjectScanner:
    def __init__(self, root: Path, ignore_patterns: bool = True):
        self.root = root
        self.ignore_patterns = ignore_patterns
        self.spec = self._load_gitignore()

    def _load_gitignore(self) -> Optional[pathspec.PathSpec]:
        if not self.ignore_patterns:
            return None

        patterns = [
            ".git/",
            ".idea/",
            "__pycache__/",
            "venv/",
            ".venv/",
            "node_modules/",
            ".DS_Store",
        ]
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            try:
                with open(gitignore, "r", encoding="utf-8") as f:
                    patterns.extend(f.readlines())
            except OSError:
                pass

        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def scan(self) -> List[FileNode]:
        results = []

        for root, dirs, files in os.walk(self.root):
            rel_root = Path(root).relative_to(self.root)

            # Filter dirs
            if self.spec:
                dirs[:] = [
                    d for d in dirs if not self.spec.match_file(str(rel_root / d))
                ]

            for file in files:
                rel_path = rel_root / file
                if self.spec and self.spec.match_file(str(rel_path)):
                    continue

                full_path = Path(root) / file
                # Добавляем try-except для st_size на случай проблем с доступом
                try:
                    size = full_path.stat().st_size
                except OSError:
                    size = 0

                node = FileNode(
                    name=file,
                    path=full_path,
                    rel_path=rel_path,
                    is_dir=False,
                    size=size,
                )
                results.append(node)

        return results
