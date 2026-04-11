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
    normalized: bool = False


@dataclass
class DiffParseResult:
    """Результат парсинга ответа модели."""

    blocks: list[DiffBlock] = field(default_factory=list)
    unparsed_text: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class _MatchInfo:
    """Результат поиска совпадения search-фрагмента в содержимом файла."""

    count: int  # 0, 1 или >1
    normalized: bool = False
    norm_details: Optional[dict] = None


class DiffEngine:
    """Парсинг и применение диффов."""

    # Паттерны для построчного парсинга
    _FILE_HEADER = re.compile(r"^## File:\s*`?([^`\n]+?)`?\s*$")
    _FENCE = re.compile(r"^\s*`{3,}")

    @classmethod
    def _validate_path(cls, file_path: str, project_root: Path) -> Path:
        """Проверить путь на отсутствие path traversal и вернуть абсолютный путь."""
        resolved = (project_root / file_path).resolve()
        if not resolved.is_relative_to(project_root.resolve()):
            raise ValueError(f"Path traversal detected: {file_path}")
        return resolved

    @classmethod
    def _try_match(cls, content: str, search: str) -> _MatchInfo:
        """Найти совпадение search в content с fallback на нормализацию whitespace.

        Используется единообразно в apply_block, dry_run и preview
        для предотвращения рассинхрона между проверкой и применением.
        """
        count = content.count(search)
        if count == 1:
            return _MatchInfo(count=1)
        if count > 1:
            return _MatchInfo(count=count)

        # Fallback: нормализация trailing whitespace в строках
        norm_content = "\n".join(l.rstrip() for l in content.split("\n"))
        norm_search = "\n".join(l.rstrip() for l in search.split("\n"))
        norm_count = norm_content.count(norm_search)

        if norm_count == 1:
            idx = norm_content.index(norm_search)
            # rstrip() не удаляет \n, только trailing whitespace,
            # поэтому кол-во строк совпадает с оригиналом
            before_lines = norm_content[:idx].count("\n")
            search_line_count = search.count("\n") + 1
            return _MatchInfo(
                count=1,
                normalized=True,
                norm_details={
                    "before_lines": before_lines,
                    "search_line_count": search_line_count,
                },
            )

        return _MatchInfo(count=0)

    @classmethod
    def _apply_normalized(
        cls, content: str, search: str, replace: str, norm_details: dict
    ) -> str:
        """Применить замену по нормализованным координатам к оригинальному контенту."""
        original_lines = content.split("\n")
        before = norm_details["before_lines"]
        count = norm_details["search_line_count"]
        new_lines = (
            original_lines[:before]
            + replace.split("\n")
            + original_lines[before + count :]
        )
        return "\n".join(new_lines)

    @classmethod
    def parse(cls, text: str) -> DiffParseResult:
        """Парсит ответ модели, извлекая SEARCH/REPLACE блоки.

        Использует построчный state-machine парсер с отслеживанием глубины
        вложенности маркеров, что позволяет корректно обрабатывать
        диффы, содержащие примеры формата внутри себя.
        """
        result = DiffParseResult()
        # Нормализация переносов строк для Windows/macOS
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        i = 0

        state = "IDLE"  # IDLE → EXPECT_SEARCH → IN_SEARCH → IN_REPLACE
        file_path = ""
        search_lines: list[str] = []
        replace_lines: list[str] = []
        depth = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if state == "IDLE":
                # Пропускаем закрывающие code fences от предыдущих блоков
                if cls._FENCE.match(line):
                    i += 1
                    continue
                m = cls._FILE_HEADER.match(line)
                if m:
                    file_path = m.group(1).strip()
                    state = "EXPECT_SEARCH"

            elif state == "EXPECT_SEARCH":
                # Пропускаем опциональный открывающий/закрывающий code fence
                if cls._FENCE.match(line):
                    i += 1
                    continue
                if stripped == "<<<<<<< SEARCH":
                    if not file_path:
                        result.warnings.append(
                            f"Block at line {i + 1}: missing ## File: header, skipping"
                        )
                        i += 1
                        continue
                    state = "IN_SEARCH"
                    search_lines = []
                    replace_lines = []
                    depth = 1
                else:
                    m = cls._FILE_HEADER.match(line)
                    if m:
                        file_path = m.group(1).strip()
                        # state остаётся EXPECT_SEARCH

            elif state == "IN_SEARCH":
                if stripped == "<<<<<<< SEARCH":
                    depth += 1
                    search_lines.append(line)
                elif stripped == "=======" and depth == 1:
                    state = "IN_REPLACE"
                    replace_lines = []
                elif stripped == ">>>>>>> REPLACE":
                    depth -= 1
                    if depth == 0:
                        # Малформат: REPLACE до =======
                        result.warnings.append(
                            f"Block for {file_path}: >>>>>>> REPLACE found before =======, "
                            "replace will be empty"
                        )
                        cls._add_block(result, file_path, search_lines, replace_lines)
                        file_path = ""  # Сброс для следующего блока
                        state = "IDLE"
                    else:
                        search_lines.append(line)
                else:
                    search_lines.append(line)

            elif state == "IN_REPLACE":
                if stripped == "<<<<<<< SEARCH":
                    depth += 1
                    replace_lines.append(line)
                elif stripped == ">>>>>>> REPLACE":
                    depth -= 1
                    if depth == 0:
                        cls._add_block(result, file_path, search_lines, replace_lines)
                        file_path = ""  # Сброс для следующего блока
                        state = "IDLE"
                    else:
                        replace_lines.append(line)
                else:
                    replace_lines.append(line)

            i += 1

        # Проверка незакрытых блоков
        if state in ("IN_SEARCH", "IN_REPLACE"):
            result.warnings.append(
                f"Unclosed block for {file_path} — input ended in state {state}, block discarded"
            )

        if not result.blocks:
            result.unparsed_text = text
            result.warnings.append(
                "No SEARCH/REPLACE blocks found. "
                "Model output might not follow the expected format."
            )

        return result

    @classmethod
    def _add_block(
        cls,
        result: DiffParseResult,
        file_path: str,
        search_lines: list[str],
        replace_lines: list[str],
    ) -> None:
        """Создать и добавить DiffBlock в результат."""
        search = "\n".join(search_lines)
        replace = "\n".join(replace_lines)

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

    @classmethod
    def apply_block(cls, block: DiffBlock, project_root: Path) -> DiffBlock:
        """Применить один блок замены к файлу."""
        try:
            file_path = cls._validate_path(block.file_path, project_root)
        except ValueError as e:
            block.error = str(e)
            return block

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

        match = cls._try_match(content, block.search)

        if match.count == 0:
            block.error = "SEARCH block not found in file. Check exact whitespace."
            return block

        if match.count > 1:
            block.error = (
                f"SEARCH block found {match.count} times — ambiguous. "
                "Make the snippet more unique."
            )
            return block

        # count == 1
        block.normalized = match.normalized

        if match.normalized and match.norm_details:
            new_content = cls._apply_normalized(
                content, block.search, block.replace, match.norm_details
            )
        else:
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

            try:
                file_path = cls._validate_path(block.file_path, project_root)
            except ValueError as e:
                result.error = str(e)
                results.append(result)
                continue

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
                    match = cls._try_match(content, block.search)
                    result.normalized = match.normalized
                    if match.count == 0:
                        result.error = "SEARCH block not found"
                    elif match.count > 1:
                        result.error = f"SEARCH block found {match.count} times"
                    else:
                        result.applied = True
                except Exception as e:
                    result.error = str(e)

            results.append(result)

        return results

    @classmethod
    def preview(cls, block: DiffBlock, project_root: Path) -> dict:
        """Предпросмотр одного блока."""
        try:
            file_path = cls._validate_path(block.file_path, project_root)
        except ValueError as e:
            return {"error": str(e)}

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

        match = cls._try_match(content, block.search)

        if match.count == 0:
            return {
                "error": "SEARCH block not found",
                "file_content_preview": content[:500],
            }

        if match.count > 1:
            return {
                "error": f"SEARCH block found {match.count} times — ambiguous",
            }

        # count == 1
        if match.normalized and match.norm_details:
            new_content = cls._apply_normalized(
                content, block.search, block.replace, match.norm_details
            )
        else:
            new_content = content.replace(block.search, block.replace, 1)

        return {
            "before": content,
            "after": new_content,
            "search": block.search,
            "replace": block.replace,
            "normalized": match.normalized,
        }

    @classmethod
    def _backup_files(cls, blocks: list[DiffBlock], project_root: Path):
        """Создать .bak копии затронутых файлов."""
        backed_up: set[str] = set()
        for block in blocks:
            if block.file_path in backed_up or block.is_new_file:
                continue
            try:
                file_path = cls._validate_path(block.file_path, project_root)
            except ValueError:
                logger.warning("Skipping backup for unsafe path: %s", block.file_path)
                continue
            if file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                try:
                    shutil.copy2(file_path, backup_path)
                    backed_up.add(block.file_path)
                    logger.info("Backed up: %s", backup_path)
                except Exception as e:
                    logger.warning("Failed to backup %s: %s", file_path, e)
