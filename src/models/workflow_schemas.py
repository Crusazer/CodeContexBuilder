"""Модели данных для воркфлоу."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    SKIPPED = "skipped"


class StepRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    ARCHITECT = "architect"
    WORKER = "worker"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"


class WorkflowStep(BaseModel):
    """Один шаг воркфлоу."""

    id: int
    name: str
    role: StepRole
    description: str = ""
    suggested_skills: list[str] = Field(default_factory=list)
    suggested_rules: list[str] = Field(default_factory=list)
    suggested_output_format: Optional[str] = None
    context_patterns: list[str] = Field(default_factory=list)
    context_mode: str = "full"
    status: StepStatus = StepStatus.PENDING
    result_text: str = ""
    notes: str = ""


class Workflow(BaseModel):
    """Полный воркфлоу."""

    name: str
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    current_step_index: int = 0

    @property
    def current_step(self) -> Optional[WorkflowStep]:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def progress(self) -> str:
        done = sum(
            1 for s in self.steps if s.status in (StepStatus.DONE, StepStatus.SKIPPED)
        )
        return f"{done}/{len(self.steps)}"

    def advance(self) -> Optional[WorkflowStep]:
        self.current_step_index += 1
        if self.current_step:
            self.current_step.status = StepStatus.ACTIVE
        return self.current_step


# ─── Встроенные воркфлоу ───

_WORKFLOW_NEW_FEATURE = Workflow(
    name="New Feature",
    description="Полный цикл добавления новой фичи",
    steps=[
        WorkflowStep(
            id=1,
            name="Планирование",
            role=StepRole.ORCHESTRATOR,
            description="Разбить задачу на шаги. Определить затронутые файлы и порядок изменений.",
            suggested_output_format="plan-only",
            context_mode="skeleton",
        ),
        WorkflowStep(
            id=2,
            name="Архитектура",
            role=StepRole.ARCHITECT,
            description="Спроектировать решение. Определить интерфейсы и зависимости.",
            suggested_skills=["clean-architecture"],
            suggested_output_format="plan-only",
            context_mode="skeleton",
        ),
        WorkflowStep(
            id=3,
            name="Реализация",
            role=StepRole.WORKER,
            description="Написать код согласно плану архитектора.",
            suggested_rules=["no-placeholders", "preserve-existing"],
            suggested_output_format="search-replace-blocks",
            context_mode="full",
        ),
        WorkflowStep(
            id=4,
            name="Ревью",
            role=StepRole.REVIEWER,
            description="Проверить написанный код на ошибки и соответствие плану.",
            context_mode="full",
        ),
    ],
)

_WORKFLOW_BUG_FIX = Workflow(
    name="Bug Fix",
    description="Быстрое исправление бага",
    steps=[
        WorkflowStep(
            id=1,
            name="Диагностика и фикс",
            role=StepRole.DEBUGGER,
            description="Найти причину бага и исправить с минимальными изменениями.",
            suggested_rules=["minimal-changes", "no-placeholders"],
            suggested_output_format="search-replace-blocks",
            context_mode="full",
        ),
    ],
)

_WORKFLOW_REFACTOR = Workflow(
    name="Refactor",
    description="Рефакторинг существующего кода",
    steps=[
        WorkflowStep(
            id=1,
            name="Анализ",
            role=StepRole.ARCHITECT,
            description="Проанализировать код и предложить план рефакторинга.",
            suggested_output_format="plan-only",
            context_mode="skeleton",
        ),
        WorkflowStep(
            id=2,
            name="Выполнение",
            role=StepRole.WORKER,
            description="Выполнить рефакторинг по плану.",
            suggested_rules=["no-placeholders", "preserve-existing"],
            suggested_output_format="search-replace-blocks",
            context_mode="full",
        ),
    ],
)

BUILTIN_WORKFLOWS: dict[str, Workflow] = {
    "new-feature": _WORKFLOW_NEW_FEATURE,
    "bug-fix": _WORKFLOW_BUG_FIX,
    "refactor": _WORKFLOW_REFACTOR,
}
