"""Модели данных для системы сборки промптов."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.core.token_counter import TokenCounter


class TemplateCategory(str, Enum):
    ROLE = "roles"
    SKILL = "skills"
    RULE = "rules"
    OUTPUT_FORMAT = "output_formats"


class Template(BaseModel):
    """Один шаблон (роль/скилл/правило/формат)."""

    name: str
    category: TemplateCategory
    display_name: str
    content: str
    file_path: Path
    description: str = ""
    tags: list[str] = Field(default_factory=list)

    @property
    def token_estimate(self) -> int:
        """Оценка токенов."""
        return TokenCounter.estimate(self.content)

    class Config:
        frozen = False


class PromptAssembly(BaseModel):
    """Результат сборки промпта из кусочков."""

    role: Optional[Template] = None
    skills: list[Template] = Field(default_factory=list)
    rules: list[Template] = Field(default_factory=list)
    output_format: Optional[Template] = None
    context_text: str = ""
    task_text: str = ""
    extra_instructions: str = ""

    @property
    def assembled_prompt(self) -> str:
        """Собирает финальный промпт."""
        sections: list[str] = []

        if self.role:
            sections.append(self._section("ROLE", self.role.content))

        if self.skills:
            skill_parts = []
            for skill in self.skills:
                skill_parts.append(f"\n## {skill.display_name}\n\n{skill.content}")
            sections.append(
                self._section(
                    "TECHNICAL CONTEXT & SKILLS",
                    "\n".join(skill_parts),
                )
            )

        if self.rules:
            rule_parts = []
            for rule in self.rules:
                rule_parts.append(f"\n## {rule.display_name}\n\n{rule.content}")
            sections.append(
                self._section(
                    "RULES & CONSTRAINTS",
                    "\n".join(rule_parts),
                )
            )

        if self.output_format:
            sections.append(self._section("OUTPUT FORMAT", self.output_format.content))

        if self.extra_instructions:
            sections.append(
                self._section(
                    "INSTRUCTIONS FROM PREVIOUS STEP",
                    self.extra_instructions,
                )
            )

        if self.context_text:
            sections.append(self._section("PROJECT CODE", self.context_text))

        if self.task_text:
            sections.append(self._section("TASK", self.task_text))

        return "\n\n".join(sections)

    @staticmethod
    def _section(title: str, content: str) -> str:
        sep = "=" * 60
        return f"{sep}\n# {title}\n{sep}\n\n{content}"

    @property
    def total_token_estimate(self) -> int:
        return TokenCounter.estimate(self.assembled_prompt)

    def get_breakdown(self) -> dict[str, int]:
        """Разбивка токенов по секциям."""
        est = TokenCounter.estimate
        breakdown: dict[str, int] = {}

        if self.role:
            breakdown["role"] = est(self.role.content)
        else:
            breakdown["role"] = 0

        breakdown["skills"] = sum(est(s.content) for s in self.skills)
        breakdown["rules"] = sum(est(r.content) for r in self.rules)

        if self.output_format:
            breakdown["output_format"] = est(self.output_format.content)
        else:
            breakdown["output_format"] = 0

        breakdown["context"] = est(self.context_text)
        breakdown["task"] = est(self.task_text)
        breakdown["extra"] = est(self.extra_instructions)
        return breakdown
