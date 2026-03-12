"""Движок воркфлоу — управляет последовательностью шагов."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from src.models.workflow_schemas import (
    Workflow,
    WorkflowStep,
    StepStatus,
    BUILTIN_WORKFLOWS,
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Управляет жизненным циклом воркфлоу."""

    def __init__(self, workspaces_dir: Path):
        self.workspaces_dir = workspaces_dir
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._active_workflow: Optional[Workflow] = None

    @property
    def active_workflow(self) -> Optional[Workflow]:
        return self._active_workflow

    @property
    def current_step(self) -> Optional[WorkflowStep]:
        if self._active_workflow:
            return self._active_workflow.current_step
        return None

    @property
    def is_active(self) -> bool:
        return self._active_workflow is not None

    # ─── Lifecycle ───

    def start_workflow(self, workflow_key: str) -> Workflow:
        """Запустить встроенный воркфлоу."""
        if workflow_key not in BUILTIN_WORKFLOWS:
            raise ValueError(f"Unknown workflow: {workflow_key}")

        template = BUILTIN_WORKFLOWS[workflow_key]
        self._active_workflow = template.model_copy(deep=True)

        if self._active_workflow.steps:
            self._active_workflow.steps[0].status = StepStatus.ACTIVE

        logger.info("Started workflow: %s", workflow_key)
        return self._active_workflow

    def start_custom_workflow(self, workflow: Workflow) -> Workflow:
        """Запустить кастомный воркфлоу."""
        self._active_workflow = workflow.model_copy(deep=True)
        if self._active_workflow.steps:
            self._active_workflow.steps[0].status = StepStatus.ACTIVE
        return self._active_workflow

    def advance_step(self, result_text: str = "") -> Optional[WorkflowStep]:
        """Завершить текущий шаг и перейти к следующему."""
        if not self._active_workflow:
            return None

        current = self.current_step
        if current:
            current.status = StepStatus.DONE
            current.result_text = result_text

        next_step = self._active_workflow.advance()
        if next_step:
            logger.info("Advanced to step: %s", next_step.name)
        return next_step

    def skip_step(self) -> Optional[WorkflowStep]:
        """Пропустить текущий шаг."""
        if not self._active_workflow:
            return None

        current = self.current_step
        if current:
            current.status = StepStatus.SKIPPED

        return self._active_workflow.advance()

    def complete_workflow(self):
        """Завершить воркфлоу."""
        if self._active_workflow:
            for step in self._active_workflow.steps:
                if step.status == StepStatus.ACTIVE:
                    step.status = StepStatus.DONE
            logger.info("Workflow completed: %s", self._active_workflow.name)
        self._active_workflow = None

    def get_previous_results(self) -> list[tuple[WorkflowStep, str]]:
        """Получить результаты всех завершённых шагов."""
        if not self._active_workflow:
            return []

        results = []
        current = self.current_step
        for step in self._active_workflow.steps:
            if current and step.id >= current.id:
                break
            if step.result_text and step.status == StepStatus.DONE:
                results.append((step, step.result_text))

        return results

    def get_previous_results_text(self) -> str:
        """Собрать текст результатов для подстановки в промпт."""
        results = self.get_previous_results()
        if not results:
            return ""

        parts = []
        for step, text in results:
            parts.append(f"## Result of Step {step.id}: {step.name}\n{text}")
        return "\n\n".join(parts)

    # ─── Persistence ───

    def save_workspace(self, name: str) -> Path:
        """Сохранить текущий воркфлоу в файл."""
        if not self._active_workflow:
            raise ValueError("No active workflow to save")

        file_path = self.workspaces_dir / f"{name}.json"
        data = self._active_workflow.model_dump(mode="json")
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved workspace: %s", file_path)
        return file_path

    def load_workspace(self, name: str) -> Optional[Workflow]:
        """Загрузить воркфлоу из файла."""
        file_path = self.workspaces_dir / f"{name}.json"
        if not file_path.exists():
            return None

        data = json.loads(file_path.read_text(encoding="utf-8"))
        self._active_workflow = Workflow.model_validate(data)
        logger.info("Loaded workspace: %s", file_path)
        return self._active_workflow

    def list_workspaces(self) -> list[str]:
        """Список сохранённых воркспейсов."""
        return sorted(f.stem for f in self.workspaces_dir.glob("*.json"))

    def delete_workspace(self, name: str) -> bool:
        """Удалить сохранённый воркспейс."""
        file_path = self.workspaces_dir / f"{name}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
