"""
Движок для парсинга и применения SEARCH/REPLACE блоков.

Стандартный формат:

## File: path/to/file.py
<<<<<<< SEARCH
exact original code
=======
new replacement code
>>>>>>> REPLACE
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DiffBlock:
    """Один блок замены."""

    file_path: str
    search: str
    replace: str
    applied: bool = False
    error: Optional[str] = None
    is_new_file: bool = False


@dataclass
class DiffParseResult:
    """Результат парсинга ответа модели."""

    blocks: list[DiffBlock] = field(default_factory=list)
    unparsed_text: str = ""
    warnings: list[str] = field(default_factory=list)


class DiffEngine:
    """Парсинг и применение диффов."""

    # Основной паттерн: SEARCH/REPLACE
    # Поддерживает опциональные markdown code fences (``` ... ```) вокруг блоков
    PATTERN = re.compile(
        r"## File:\s*`?([^`\n]+?)`?\s*\n"
        r"(?:`{3,}[^\n]*\n)?"  # опциональный открывающий fence (```lang)
        r"<<<<<<< SEARCH\n"
        r"(.*?)"
        r"=======\n"
        r"(.*?)"
        r">>>>>>> REPLACE"
        r"(?:\n`{3,}[^\n]*)?",  # опциональный закрывающий fence
        re.DOTALL,
    )

    @classmethod
    def parse(cls, text: str) -> DiffParseResult:
        """Парсит ответ модели, извлекая SEARCH/REPLACE блоки."""
        result = DiffParseResult()

        for match in cls.PATTERN.finditer(text):
            file_path = match.group(1).strip()
            search = match.group(2)
            replace = match.group(3)

            # Убираем ровно один trailing \n если есть (артефакт формата)
            if search.endswith("\n"):
                search = search[:-1]
            if replace.endswith("\n"):
                replace = replace[:-1]

            is_new = search.strip() == ""

            block = DiffBlock(
                file_path=file_path,
                search=search,
                replace=replace,
                is_new_file=is_new,
            )
            result.blocks.append(block)

        if not result.blocks:
            result.unparsed_text = text
            result.warnings.append(
                "No SEARCH/REPLACE blocks found. "
                "Model output might not follow the expected format."
            )

        return result

    @classmethod
    def apply_block(cls, block: DiffBlock, project_root: Path) -> DiffBlock:
        """Применить один блок замены к файлу."""
        file_path = project_root / block.file_path

        # Новый файл
        if block.is_new_file:
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(block.replace, encoding="utf-8")
                block.applied = True
                logger.info("Created new file: %s", block.file_path)
            except Exception as e:
                block.error = f"Error creating file: {e}"
            return block

        # Существующий файл
        if not file_path.exists():
            block.error = f"File not found: {block.file_path}"
            return block

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            block.error = f"Error reading: {e}"
            return block

        count = content.count(block.search)

        if count == 0:
            # Попробуем с нормализацией trailing whitespace в строках
            norm_content = "\n".join(l.rstrip() for l in content.split("\n"))
            norm_search = "\n".join(l.rstrip() for l in block.search.split("\n"))

            if norm_content.count(norm_search) == 1:
                # Находим позицию в нормализованном, применяем аккуратно
                idx = norm_content.index(norm_search)
                # Восстанавливаем: считаем строки до позиции
                before_lines = norm_content[:idx].count("\n")
                search_line_count = block.search.count("\n") + 1
                original_lines = content.split("\n")
                new_lines = (
                    original_lines[:before_lines]
                    + block.replace.split("\n")
                    + original_lines[before_lines + search_line_count :]
                )
                new_content = "\n".join(new_lines)
                file_path.write_text(new_content, encoding="utf-8")
                block.applied = True
                return block

            block.error = "SEARCH block not found in file. Check exact whitespace."
            return block

        if count > 1:
            block.error = (
                f"SEARCH block found {count} times — ambiguous. "
                "Make the snippet more unique."
            )
            return block

        new_content = content.replace(block.search, block.replace, 1)

        try:
            file_path.write_text(new_content, encoding="utf-8")
            block.applied = True
        except Exception as e:
            block.error = f"Error writing: {e}"

        return block

    @classmethod
    def apply_all(
        cls,
        blocks: list[DiffBlock],
        project_root: Path,
        backup: bool = True,
    ) -> list[DiffBlock]:
        """
        Применить все блоки.
        backup=True — создаёт .bak копии перед изменением.
        """
        if backup:
            cls._backup_files(blocks, project_root)

        for block in blocks:
            cls.apply_block(block, project_root)
            if block.error:
                logger.error("Diff apply error in %s: %s", block.file_path, block.error)

        return blocks

    @classmethod
    def dry_run(cls, blocks: list[DiffBlock], project_root: Path) -> list[DiffBlock]:
        """Проверка всех блоков без применения."""
        results = []
        for block in blocks:
            result = DiffBlock(
                file_path=block.file_path,
                search=block.search,
                replace=block.replace,
                is_new_file=block.is_new_file,
            )

            file_path = project_root / block.file_path

            if block.is_new_file:
                if file_path.exists():
                    result.error = "File already exists (will be overwritten)"
                else:
                    result.applied = True  # Would succeed
            elif not file_path.exists():
                result.error = f"File not found: {block.file_path}"
            else:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    count = content.count(block.search)
                    if count == 0:
                        result.error = "SEARCH block not found"
                    elif count > 1:
                        result.error = f"SEARCH block found {count} times"
                    else:
                        result.applied = True
                except Exception as e:
                    result.error = str(e)

            results.append(result)

        return results

    @classmethod
    def preview(cls, block: DiffBlock, project_root: Path) -> dict:
        """Предпросмотр одного блока."""
        file_path = project_root / block.file_path

        if block.is_new_file:
            return {
                "is_new": True,
                "file_path": block.file_path,
                "content": block.replace,
            }

        if not file_path.exists():
            return {"error": f"File not found: {block.file_path}"}

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": str(e)}

        if block.search not in content:
            return {
                "error": "SEARCH block not found",
                "file_content_preview": content[:500],
            }

        new_content = content.replace(block.search, block.replace, 1)
        return {
            "before": content,
            "after": new_content,
            "search": block.search,
            "replace": block.replace,
        }

    @classmethod
    def _backup_files(cls, blocks: list[DiffBlock], project_root: Path):
        """Создать .bak копии затронутых файлов."""
        backed_up: set[str] = set()
        for block in blocks:
            if block.file_path in backed_up or block.is_new_file:
                continue
            file_path = project_root / block.file_path
            if file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                try:
                    shutil.copy2(file_path, backup_path)
                    backed_up.add(block.file_path)
                    logger.info("Backed up: %s", backup_path)
                except Exception as e:
                    logger.warning("Failed to backup %s: %s", file_path, e)
