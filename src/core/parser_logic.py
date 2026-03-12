"""Логика формирования контекста из выбранных файлов."""

from __future__ import annotations

from pathlib import Path

from src.core.fs_scanner import FsScanner


class ContextBuilder:
    """Собирает текстовый контекст из списка файлов."""

    @staticmethod
    def build_context(
        files: list[Path],
        project_root: Path,
        mode: str = "full",
        separator: str = "\n\n",
    ) -> str:
        """
        Собрать контекст из файлов.

        mode:
            "full"     — полное содержимое
            "skeleton" — только сигнатуры (упрощённый)
        """
        parts = []

        for file_path in sorted(files):
            try:
                rel = file_path.relative_to(project_root)
            except ValueError:
                rel = file_path

            content = FsScanner.read_file(file_path)
            if content is None:
                continue

            if mode == "skeleton":
                content = ContextBuilder._make_skeleton(content, file_path.suffix)

            header = f"## File: {rel}"
            fence_lang = ContextBuilder._lang_from_ext(file_path.suffix)
            block = f"{header}\n```{fence_lang}\n{content}\n```"
            parts.append(block)

        return separator.join(parts)

    @staticmethod
    def _make_skeleton(content: str, ext: str) -> str:
        """Извлечь только сигнатуры/структуру из файла."""
        if ext != ".py":
            # Для не-Python — возвращаем первые 50 строк
            lines = content.split("\n")
            if len(lines) > 50:
                return "\n".join(lines[:50]) + "\n# ... (truncated)"
            return content

        # Для Python — извлекаем классы, функции, импорты
        result_lines = []
        lines = content.split("\n")
        in_docstring = False
        docstring_char = None

        for line in lines:
            stripped = line.strip()

            # Трёхкавычковые строки
            if in_docstring:
                result_lines.append(line)
                if docstring_char in stripped:
                    in_docstring = False
                continue

            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_char = stripped[:3]
                result_lines.append(line)
                if stripped.count(docstring_char) >= 2:
                    continue
                in_docstring = True
                continue

            # Импорты
            if stripped.startswith(("import ", "from ")):
                result_lines.append(line)
                continue

            # Классы и функции
            if stripped.startswith(("class ", "def ", "async def ")):
                result_lines.append(line)
                # Добавить docstring если следующая строка
                continue

            # Декораторы
            if stripped.startswith("@"):
                result_lines.append(line)
                continue

            # Пустые строки между блоками
            if not stripped and result_lines and result_lines[-1].strip():
                result_lines.append(line)
                continue

            # Константы (UPPER_CASE = ...)
            if "=" in stripped and stripped.split("=")[0].strip().isupper():
                result_lines.append(line)
                continue

        return "\n".join(result_lines)

    @staticmethod
    def _lang_from_ext(ext: str) -> str:
        """Получить имя языка для code fence."""
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".sql": "sql",
            ".sh": "bash",
            ".bash": "bash",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".swift": "swift",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".vue": "vue",
            ".svelte": "svelte",
        }
        return mapping.get(ext.lower(), "")
