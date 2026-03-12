"""
Контроллер — связующее звено между UI и core.
Координирует PromptBuilder, WorkflowEngine, DiffEngine.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.config import TEMPLATES_DIR, WORKSPACES_DIR, load_settings, save_settings
from src.core.diff_engine import DiffEngine, DiffBlock, DiffParseResult
from src.core.fs_scanner import FsScanner, FileNode
from src.core.git_service import GitService  # noqa: E402 — used lazily
from src.core.parser_logic import ContextBuilder
from src.core.prompt_builder import PromptBuilder
from src.core.template_manager import TemplateManager
from src.core.token_counter import TokenCounter
from src.core.workflow_engine import WorkflowEngine
from src.models.workflow_schemas import WorkflowStep

logger = logging.getLogger(__name__)


class AppController:
    """Главный контроллер приложения."""

    def __init__(self):
        self.settings = load_settings()

        # Core-сервисы
        self.template_manager = TemplateManager(TEMPLATES_DIR)
        self.workflow_engine = WorkflowEngine(WORKSPACES_DIR)
        self.prompt_builder = PromptBuilder(self.template_manager)
        self.scanner = FsScanner()

        # Состояние
        self._project_root: Optional[Path] = None
        self._file_tree: Optional[FileNode] = None
        self._git_service: Optional[GitService] = None
        self._selected_files: list[Path] = []
        self._context_mode: str = self.settings.get("default_context_mode", "full")

    # ─── Project ───

    @property
    def project_root(self) -> Optional[Path]:
        return self._project_root

    def open_project(self, path: str | Path) -> FileNode:
        """Открыть проект и просканировать."""
        self._project_root = Path(path)
        self._file_tree = self.scanner.scan(self._project_root)
        self._git_service = GitService(self._project_root)
        self._selected_files.clear()

        self.settings["last_project_path"] = str(self._project_root)
        if str(self._project_root) not in self.settings.get("recent_projects", []):
            self.settings.setdefault("recent_projects", []).insert(
                0, str(self._project_root)
            )
            self.settings["recent_projects"] = self.settings["recent_projects"][:10]
        save_settings(self.settings)

        return self._file_tree

    @property
    def file_tree(self) -> Optional[FileNode]:
        return self._file_tree

    # ─── File Selection ───

    def get_changed_files(self) -> list[Path]:
        """Получить список изменённых файлов через GitService.

        Returns:
            List of changed file paths; empty list on any error.
        """
        paths, _ = self.select_changed_files()
        return paths

    def select_changed_files(self) -> tuple[list[Path], str | None]:
        """Получить изменённые файлы с обработкой ошибок.

        Returns:
            Tuple of (paths, error_message). error_message is None on success.
        """
        if not self._project_root or not self._git_service:
            return [], "Project root is not set."

        try:
            if not self._git_service.is_git_repo():
                return [], "Not a git repository"
            paths = self._git_service.get_changed_files()
            return paths, None
        except RuntimeError as e:
            return [], str(e)
        except Exception as e:
            logger.exception("Unexpected error getting changed files")
            return [], f"Unexpected error: {e}"

    def set_selected_files(self, files: list[Path]):
        self._selected_files = list(files)

    def get_selected_files(self) -> list[Path]:
        return self._selected_files

    @property
    def context_mode(self) -> str:
        return self._context_mode

    @context_mode.setter
    def context_mode(self, mode: str):
        self._context_mode = mode

    # ─── Context Building ───

    def build_context(self) -> str:
        """Собрать контекст из выбранных файлов."""
        if not self._project_root or not self._selected_files:
            return ""

        return ContextBuilder.build_context(
            files=self._selected_files,
            project_root=self._project_root,
            mode=self._context_mode,
        )

    # ─── Prompt Assembly ───

    def assemble_prompt(self, task: str = "", extra: str = "") -> str:
        """Полная сборка промпта."""
        context = self.build_context()
        self.prompt_builder.set_context(context)
        self.prompt_builder.set_task(task)

        # Если воркфлоу активен — добавить результаты предыдущих шагов
        if self.workflow_engine.is_active:
            prev = self.workflow_engine.get_previous_results_text()
            combined_extra = prev
            if extra:
                combined_extra += "\n\n" + extra if combined_extra else extra
            self.prompt_builder.set_extra_instructions(combined_extra)
        else:
            self.prompt_builder.set_extra_instructions(extra)

        return self.prompt_builder.get_prompt_text()

    def get_prompt_stats(self) -> dict:
        """Статистика промпта."""
        text = self.prompt_builder.get_prompt_text()
        breakdown = self.prompt_builder.get_token_breakdown()
        exact = TokenCounter.count(text)
        return {
            "total_tokens": exact,
            "total_chars": len(text),
            "breakdown": breakdown,
            "file_count": len(self._selected_files),
        }

    # ─── Workflow ───

    def start_workflow(self, key: str) -> WorkflowStep | None:
        """Запустить воркфлоу и настроить builder."""
        wf = self.workflow_engine.start_workflow(key)
        step = wf.current_step
        if step:
            self._apply_step_to_builder(step)
        return step

    def advance_workflow(self, result_text: str = "") -> WorkflowStep | None:
        """Перейти к следующему шагу."""
        next_step = self.workflow_engine.advance_step(result_text)
        if next_step:
            self._apply_step_to_builder(next_step)
        return next_step

    def skip_workflow_step(self) -> WorkflowStep | None:
        """Пропустить шаг."""
        next_step = self.workflow_engine.skip_step()
        if next_step:
            self._apply_step_to_builder(next_step)
        return next_step

    def stop_workflow(self):
        """Остановить воркфлоу."""
        self.workflow_engine.complete_workflow()

    def _apply_step_to_builder(self, step: WorkflowStep):
        """Настроить PromptBuilder согласно шагу."""
        self.prompt_builder.apply_preset(
            role=step.role.value,
            skills=step.suggested_skills,
            rules=step.suggested_rules,
            output_format=step.suggested_output_format,
        )
        self._context_mode = step.context_mode

    # ─── Diffs ───

    def parse_diffs(self, text: str) -> DiffParseResult:
        """Парсинг ответа модели."""
        return DiffEngine.parse(text)

    def dry_run_diffs(self, blocks: list[DiffBlock]) -> list[DiffBlock]:
        """Проверка блоков без применения."""
        if not self._project_root:
            return []
        return DiffEngine.dry_run(blocks, self._project_root)

    def apply_diffs(self, blocks: list[DiffBlock]) -> list[DiffBlock]:
        """Применить блоки с бэкапом."""
        if not self._project_root:
            return []
        return DiffEngine.apply_all(blocks, self._project_root, backup=True)

    # ─── Settings ───

    def save_app_settings(self):
        save_settings(self.settings)
